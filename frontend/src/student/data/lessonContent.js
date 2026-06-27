// Static lesson data for Unit 1.
// To add new units, append to QUESTIONS and update PAGE_SUBTITLE.
export const PAGE_SUBTITLE = "Python Fundamentals · Unit 1";

export const LESSON_INTRO = "Strings in Python";
export const LESSON_BODY = ` are sequences of characters enclosed in single or double
quotes. They are immutable — once created they cannot be changed in place,
but you can always create new strings from them.

── Slicing ──────────────────────
s[start : end]   extract a portion
s[0:3]           first three chars
s[-3:]           last three chars
s[::2]           every other char

── Common Methods ───────────────
.upper()   .lower()   .strip()
.split()   .join()    .replace()
.find()    .count()   .startswith()

`;

export const QUESTIONS = [
  {
    unit: "Unit 1.0",
    text: 'Slice the first three characters from the string: word = "cheese"',
    accepted: ['word[:3]', '"word"[:3]', "'word'[:3]"],
    hint: 'Try square-bracket slice notation → string[start:end]\nExample: "hello"[0:2] gives "he"',
  },
  {
    unit: "Unit 1.1",
    text: 'Convert the string: greeting = "hello" to uppercase.',
    accepted: ['"greeting".upper()', "'greeting'.upper()", "greeting.upper()"],
    hint: "String objects have a built-in method that returns an uppercase copy.",
  },
  {
    unit: "Unit 1.2",
    text: 'Get the length of the string: language = "python".',
    accepted: ['len(language)', "len(language)", "len(language)"],
    hint: "Python has a built-in function that counts items in any sequence.",
  },
];
