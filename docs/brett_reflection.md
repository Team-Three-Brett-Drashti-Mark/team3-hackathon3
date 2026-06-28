# Retrospective — Brett Coleman (Front-End Engineer)

This is my honest look back at Pathwise, our private learning assistant. I want to be straight about what we set out to build, where we ended up somewhere different, and the calls I would make differently if I had the time back. This is not a victory lap. We shipped something I am proud of, but the interesting parts of any build are the places where the plan and reality stopped agreeing with each other.

## What We Planned at the Hackathon

Going into the hackathon, the plan was pretty clean on paper. Our problem statement was that cohort programs have no scalable way to help students learn through guided support without just handing over answers, and instructors and admins have almost no visibility into where students are actually struggling. So we scoped Phase 1 around proving the core loop, not polishing it.

The Phase 1 MVP scope we agreed on was:

- Curriculum ingestion into a searchable knowledge base (PDF, Markdown, text), chunked and embedded into a vector store.
- A student chat assistant doing real RAG retrieval against the curriculum, with guided responses only and no direct answers.
- A guardrail escalation path: attempt one gives a hint and a clarifying question, attempt two gives step by step guidance without the final answer, attempt three refuses and redirects to concept review.
- Basic logging of the query, the response, the timestamp, and the attempt count.
- Basic role access, meaning a student login and an admin login.

The tech stack we committed to was a Python and FastAPI backend, RAG implemented for real and not stubbed, React on the front end, GitHub for CI/CD, and Databricks in the mix. The vector database was listed as an open choice between FAISS, Pinecone, PGVector, or Chroma. The LLM was meant to be a local model or an API, with the note that API use needed a cost justification.

My piece of this was the front end and the overall student and admin experience. The pitch I gave framed it as a simple ask-and-get-guidance flow for students, and a non-technical dashboard for admins that surfaces what topics get asked about, where students get stuck, and where the system is blocking answer-seeking behavior.

## What Changed and Why

A fair amount changed between that plan and what is actually running. Some of it was good adaptation. Some of it was us quietly trading scope to hit the deadline, and I want to name those honestly rather than pretend they were always intentional.

### We went with Databricks Vector Search, not the listed options

The plan left the vector DB open between FAISS, Pinecone, PGVector, and Chroma. We ended up using Databricks Vector Search instead. The reason was simple: Databricks was already a required part of our stack, our whole Bronze, Silver, Gold pipeline lived there, and our logging was going into a Delta table under Unity Catalog. Splitting the vector store off into a separate service would have meant managing another system, another set of credentials, and another place for the curriculum to drift out of sync. Keeping retrieval next to the governed data was the lower-risk call, so we made it.

### We picked an API model and had to own that tradeoff

The stack note said an API model needed cost justification. We went with Groq running llama-3.1-8b-instant. The justification was speed of iteration and response latency during a short build window. A hosted API meant we were not babysitting model infrastructure on top of everything else, and the per-call cost at our usage was negligible. The honest tradeoff is that we took on an external dependency and a vendor we do not control, which matters more for a real deployment than it did for a demo.

### Hosting moved from Databricks Apps to Render

This was the biggest mid-build pivot and it is right there in the commit history. We first wired the app to run on Databricks Apps, including pinning the auth type so retrieval and logging would work in that environment. Then we pulled the app manifest out and moved the whole web tier to Render as a single public web service, with the data and retrieval backend staying in Databricks.

The reason was practical. Getting a clean, shareable public URL with the front end and back end on one origin was simpler on Render, and it removed a class of cross-origin and auth headaches we were fighting. FastAPI now serves the built React bundle and the APIs from the same place, so the front end just calls relative paths and it works in dev and in production without environment-specific URL juggling. The data layer never left Databricks, so we kept the governance and lost the deployment friction. I think this was the right move, but it was a reaction to pain, not something we foresaw at the hackathon.

### Role-based login did not get built

This is the one I most want to be honest about. Student login and admin login were explicitly in Phase 1 scope, and we did not build authentication. There is no auth layer in the shipped product. The admin dashboard and the student app are just different routes.

That gap forced a second decision in the logging design. Because there was no identity to attach to, we log an anonymous session ID per question instead of a user. We wrote that up as a deliberate privacy stance, and there is a real argument there: storing PII without a retention and access policy creates liability before it creates value, and some students could be minors. All of that is true. But I do not want to dress up a cut corner as pure principle. We did not get to auth, and the anonymous session model was partly the principled choice and partly the choice that let us ship without auth. Both things are true at once.

### The guardrail got more layered than the original counter

The hackathon version of the guardrail was basically an attempt counter with three escalating responses. What we built is more layered. We separated genuine curriculum questions from answer-seeking attempts using an intent classifier, added answer-leak detection with static fallbacks so the model cannot quietly leak a solution, and made the escalation respond to intent rather than just a raw count. This was a good change driven by actually using the thing and watching it get talked around.

It also exposed a real bug, which I think is worth recording because it is the honest version of how this went. Our off-topic detection started as a denylist of English keywords. Looking through the logs, we found non-English messages and emoji-only messages sailing past it and getting full LLM responses, because a list of English words cannot match text that has no English words in it. We fixed it by gating on whether a message contains any Latin-script letter at all before it can reach the model. The fix is solid, but the lesson is that our first guardrail design was naive, and we only caught it because we went back and read our own logs.

### The Admin Ask tab shipped as a shell

The natural-language Ask interface for admins is in the product, but only as UI. The page, the navigation, and the copy are all there, and the query backend is deferred to Phase 2. I built the front end for it knowing the backend was not ready. I am a little uncomfortable with that, because a scaffolded tab can look more finished than it is. We were clear about it in our docs, but if I am grading myself honestly, shipping a visible feature with no engine behind it is a thing I did to make the surface look complete.

## What I Would Do Differently

A few things, and they mostly come back to sequencing and not letting the demo dictate the design.

**Build auth first, or cut it from scope out loud.** Leaving login as a someday item is what pushed the anonymous-session compromise onto the logging design. If I were doing it again I would either stand up a lightweight email-only login early so identity existed from the start, or I would remove role access from the Phase 1 scope explicitly so we were not quietly carrying a commitment we never funded. Carrying it on paper and not in code is the worst of both.

**Design the intent classifier as a real classifier from day one.** The English keyword denylist was fast to write and fragile in exactly the ways you would expect. Starting from something more robust, even a small model call or a proper language and content check, would have saved us from shipping a guardrail that let emoji and non-English text straight through to the LLM. We caught it, but a paying program would have caught it first.

**Decide hosting before wiring auth to it.** We spent effort making the app work on Databricks Apps and then moved to Render. Some of that work was throwaway. If we had pinned down where this was going to live before we integrated against a specific platform's auth model, we would not have built and then unbuilt the same plumbing.

**Either finish a feature or do not show it.** The Ask tab is the clearest case. Next time I would rather ship one fewer visible surface than ship a convincing-looking shell. A clearly labeled "coming in Phase 2" placeholder is honest; a fully styled tab that does nothing is closer to a magic trick.

**Invest in CI that actually runs the tests.** Right now CI mainly compiles the code, and we have known pre-existing pollution in a couple of the test modules that we worked around rather than fixed. For a short hackathon that is a defensible call. As an ongoing product it is debt, and I would put the work in to get a green, trustworthy test run gating merges rather than leaning on it passing on a clean checkout.

## Closing Thought

The core thing we promised, a system that guides students through their own curriculum instead of answering for them and gives admins a window into where learning breaks down, is real and it works. I am genuinely happy with that. But the honest story of this build is a series of tradeoffs under a clock: we swapped the vector store to reduce moving parts, moved hosting to escape deployment friction, layered up a guardrail only after watching people slip past it, and quietly let auth and the Ask backend slide to keep the core loop on schedule. The product is good. The retrospective worth keeping is the list of places where the plan and the deadline negotiated, and who won.
