/** Number, time and date formatting. One place, so the whole UI counts the same way. */

/** The pipeline's own reading speed (privascore.textstats), so the input estimate and the
 *  result's reading_minutes agree. */
export const WORDS_PER_MINUTE = 238;

const nf = new Intl.NumberFormat();

export const num = (n: number): string => nf.format(n);

/** Rough word count for the live counter, before anything is sent. */
export const countWords = (text: string): number => (text.match(/\S+/g) ?? []).length;

export const readingMinutes = (text: string): number =>
  Math.max(1, Math.round(countWords(text) / WORDS_PER_MINUTE));

/** mm:ss for the elapsed timer. */
export const elapsed = (ms: number): string => {
  const total = Math.floor(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};

export const localDateTime = (iso: string): string =>
  new Date(iso).toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });

export const percent = (fraction: number): string => `${Math.round(fraction * 100)}%`;

export const localDate = (iso: string): string =>
  new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
