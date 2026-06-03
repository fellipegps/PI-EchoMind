export function splitSentences(text: string): [string[], string] {
  const re = /[.!?]+(?:\s|$)/g;
  const sentences: string[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    const sentence = text.slice(lastIndex, match.index + match[0].length).trim();
    if (sentence) sentences.push(sentence);
    lastIndex = match.index + match[0].length;
  }

  return [sentences, text.slice(lastIndex)];
}

