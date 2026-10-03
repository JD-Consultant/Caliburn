/** The mark that tells the two authors apart in the log (Cloudscape chat: an avatar per author). */
const glyphs = { consultant: '顧', employee: '員' } as const;

export function SpeakerAvatar({ speaker }: { speaker: keyof typeof glyphs }) {
  return (
    <span className={`msg-avatar msg-avatar--${speaker}`} aria-hidden="true">
      {glyphs[speaker]}
    </span>
  );
}
