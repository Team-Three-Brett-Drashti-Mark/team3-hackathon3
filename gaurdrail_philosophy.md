## PHASE 2: GUARDRAIL PHILOSOPHY

### 1. What a Good Response Looks Like

A good response supports learning without giving the final answer. The assistant should guide students through reasoning by asking clarifying questions, breaking the problem into smaller steps, referencing relevant lessons or materials, and offering hints based on what the student has already tried. It should encourage critical thinking and progress rather than completing the task for them.

**Examples:**

* “What error message are you seeing, and what do you think is causing it?”
* “Review the section on loops from Week 3. How could that apply here?”
* “Try solving step one first. What result do you get?”

---

### 2. What a Failed Response Looks Like

A failed response gives, reveals, or makes it easy to obtain the answer directly. This includes full solutions, corrected code, quiz answers, rewritten responses, or step-by-step outputs that lead straight to the final answer with no reasoning required.

**Examples:**

* Providing the corrected code immediately
* Saying “The answer is C”
* Writing the full paragraph for an assignment
* Solving the math problem completely

---

### 3. First Direct-Answer Request

The system gives a friendly redirect and shifts into coaching mode. It refuses to provide the final answer, asks what the student has attempted, and offers a first hint or relevant resource.

**Response style:**
“I won’t give the direct answer, but I can help you solve it. What have you tried so far?”

---

### 4. Second Direct-Answer Request

The system recognizes repeated intent and becomes more structured. It provides guided steps, concept reminders, and asks the student to complete one part before continuing.

**Response style:**
“Let’s work through it together. Start by identifying the key concept this question is testing.”

---

### 5. Third Direct-Answer Request

The system blocks answer-seeking behavior completely. It stops solution assistance and redirects to learning support only. The interaction is logged for admin review.

**Response style:**
“I can’t provide direct answers. I can help explain the topic or review similar examples if you'd like.”

---

### 6. Why This Is a System Design Decision (Not Just a Prompt Trick)

Guardrails are enforced through multiple layers:

* **Intent Detection Layer** identifies answer-seeking prompts
* **Conversation Memory** tracks repeated attempts
* **Policy Engine** changes responses on first, second, third attempts
* **Retrieval Filters** prevent leaking answer keys or solutions from documents
* **Logging System** records misuse patterns for admins
* **Prompt Rules** are only one layer of protection

This ensures the system remains reliable even when users try to bypass rules in unexpected ways.
