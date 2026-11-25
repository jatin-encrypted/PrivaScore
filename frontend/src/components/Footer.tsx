import { copy } from "../lib/copy";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-rule lg:mt-24">
      <div className="mx-auto max-w-[1440px] px-4 py-8 sm:px-6 lg:px-10">
        <p className="t-small max-w-[68ch] text-ink-3">{copy.footer}</p>
      </div>
    </footer>
  );
}
