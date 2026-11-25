import { copy } from "../lib/copy";

/**
 * 64px tall, wordmark left, links right, 2px rule below. One line at every width (section 8.4).
 * No eyebrow labels, no icons in the wordmark (section 8.8).
 */
export function Header() {
  return (
    <header className="border-b-2 border-rule-strong bg-bg">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-4 sm:px-6 lg:px-10">
        <span
          className="text-xl leading-none"
          style={{ fontStretch: "125%", fontWeight: 900 }}
        >
          {copy.brand}
        </span>
        <nav className="flex items-center gap-5">
          <a className="t-small text-ink-2 underline decoration-1 underline-offset-[3px] hover:decoration-2" href="#how-to-read">
            {copy.nav.howItWorks}
          </a>
          <a
            className="t-small text-ink-2 underline decoration-1 underline-offset-[3px] hover:decoration-2"
            href="https://github.com/jatin-encrypted/PrivaScore"
            target="_blank"
            rel="noreferrer noopener"
          >
            {copy.nav.github}
          </a>
        </nav>
      </div>
    </header>
  );
}
