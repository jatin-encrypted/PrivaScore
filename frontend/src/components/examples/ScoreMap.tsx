import { useId } from "react";

import type { ExampleSummary } from "../../api/client";
import { copy } from "../../lib/copy";

/**
 * The 15 saved policies on the two score axes, with an optional "this policy" marker.
 *
 * Why a map and not a rank: section 9 forbids a single combined score, so there is no honest
 * one-dimensional order to put these in. Two axes show the same data without inventing one,
 * and they make the point the copy keeps making, that the scores are read together.
 *
 * Drawn as inline SVG in the Redline system: square points and a hairline grid, with colours
 * from the CSS tokens so it follows the theme with no JS media query.
 *
 * The current policy is marked in --ink, NOT in --signal: section 8.2 reserves the red for risk
 * and evidence, and "where you are on a chart" is neither. It is told apart by three cues that
 * are not colour (a larger square, a heavier fill, and a crosshair to the axes), so it still
 * reads for anyone who cannot separate the two greys.
 *
 * It carries one summary label rather than 15 announceable points, because every number it
 * plots is also in the table beside it.
 */
const PAD = { top: 16, right: 16, bottom: 44, left: 52 };
const PLOT = 320;                       // the square plot area, in SVG user units
const W = PAD.left + PLOT + PAD.right;
const H = PAD.top + PLOT + PAD.bottom;
const TICKS = [0, 25, 50, 75, 100];

/** Score (0-100) to SVG coordinates. Quality is inverted because SVG y grows downward. */
const sx = (risk: number) => PAD.left + (risk / 100) * PLOT;
const sy = (quality: number) => PAD.top + (1 - quality / 100) * PLOT;

export type MapPoint = { risk: number; quality: number; label: string };

export function ScoreMap({
  examples,
  current,
}: {
  examples: ExampleSummary[];
  current?: MapPoint | undefined;
}) {
  const titleId = useId();

  const summary = current
    ? `${copy.map.heading}. ${copy.map.youAreHere(current.label)}: ${copy.map.xAxis} ${Math.round(current.risk)}, ${copy.map.yAxis} ${Math.round(current.quality)}.`
    : `${copy.map.heading}. ${examples.length} policies.`;

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="block h-auto w-full max-w-[460px]"
        role="img"
        aria-labelledby={titleId}
      >
        <title id={titleId}>{summary}</title>

        {/* Hairline grid. Stroke colours are tokens, so both themes work with no JS. */}
        <g stroke="var(--rule)" strokeWidth="1">
          {TICKS.map((t) => (
            <line key={`v${t}`} x1={sx(t)} y1={PAD.top} x2={sx(t)} y2={PAD.top + PLOT} />
          ))}
          {TICKS.map((t) => (
            <line key={`h${t}`} x1={PAD.left} y1={sy(t)} x2={PAD.left + PLOT} y2={sy(t)} />
          ))}
        </g>

        {/* The two axes themselves, heavier than the grid. */}
        <g stroke="var(--ink)" strokeWidth="2">
          <line x1={PAD.left} y1={PAD.top + PLOT} x2={PAD.left + PLOT} y2={PAD.top + PLOT} />
          <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={PAD.top + PLOT} />
        </g>

        <g className="t-code" fill="var(--ink-3)" fontSize="11">
          {TICKS.map((t) => (
            <text key={`xl${t}`} x={sx(t)} y={PAD.top + PLOT + 16} textAnchor="middle">
              {t}
            </text>
          ))}
          {TICKS.map((t) => (
            <text key={`yl${t}`} x={PAD.left - 8} y={sy(t) + 4} textAnchor="end">
              {t}
            </text>
          ))}
        </g>

        {/* The saved policies. Squares, not circles: nothing in this system is round. */}
        <g fill="var(--ink-3)">
          {examples.map((e) => (
            <rect key={e.policy_id} x={sx(e.risk_index) - 3} y={sy(e.disclosure_quality) - 3}
                  width="6" height="6" />
          ))}
        </g>

        {current ? (
          <g>
            {/* Crosshair plus a larger square, so the current policy is findable without
                relying on colour alone (contrast is not a substitute for a second cue). */}
            <g stroke="var(--ink)" strokeWidth="1" strokeDasharray="3 3">
              <line x1={PAD.left} y1={sy(current.quality)}
                    x2={sx(current.risk)} y2={sy(current.quality)} />
              <line x1={sx(current.risk)} y1={sy(current.quality)}
                    x2={sx(current.risk)} y2={PAD.top + PLOT} />
            </g>
            <rect x={sx(current.risk) - 5} y={sy(current.quality) - 5} width="10" height="10"
                  fill="var(--ink)" />
          </g>
        ) : null}

        <text x={PAD.left + PLOT / 2} y={H - 6} textAnchor="middle"
              fill="var(--ink-2)" fontSize="12">
          {copy.map.xAxis}
        </text>
        <text x={14} y={PAD.top + PLOT / 2} textAnchor="middle" fill="var(--ink-2)" fontSize="12"
              transform={`rotate(-90 14 ${PAD.top + PLOT / 2})`}>
          {copy.map.yAxis}
        </text>
      </svg>

      <figcaption className="t-small mt-3 max-w-[46ch] text-ink-3">
        {current ? (
          <>
            <span className="inline-block size-3 align-middle" style={{ background: "var(--ink)" }} />{" "}
            {copy.map.thisPolicy}.{" "}
            <span className="inline-block size-2 align-middle" style={{ background: "var(--ink-3)" }} />{" "}
            {copy.map.savedPolicy}. {copy.map.noteAxes}
          </>
        ) : (
          copy.map.noteAxes
        )}
      </figcaption>
    </figure>
  );
}
