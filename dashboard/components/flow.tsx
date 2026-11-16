import { ArrowDown, ArrowRight } from "lucide-react";

export type FlowStep = {
  title: string;
  /** One line under the title. */
  note?: string;
  /** Small label above the title, e.g. the tool that runs the step. */
  tag?: string;
};

/**
 * A left-to-right flowchart of boxes joined by arrows. On narrow screens the boxes stack
 * and the arrows point down, so it never needs sideways scrolling. An ordered list
 * underneath, so screen readers get the sequence.
 */
export function Flow({ steps, label }: { steps: FlowStep[]; label: string }) {
  return (
    <ol aria-label={label} className="flex flex-col items-stretch gap-1.5 lg:flex-row">
      {steps.map((step, i) => (
        <li key={step.title} className="flex flex-col items-stretch gap-1.5 lg:flex-1 lg:flex-row">
          {i > 0 && (
            <span className="text-muted-foreground flex items-center justify-center" aria-hidden>
              <ArrowDown className="size-4 lg:hidden" />
              <ArrowRight className="hidden size-4 lg:block" />
            </span>
          )}
          <div className="bg-card ring-foreground/10 flex-1 rounded-lg px-3 py-2.5 ring-1">
            {step.tag && (
              <p className="text-chart-1 font-mono text-[0.7rem] leading-tight">{step.tag}</p>
            )}
            <p className="text-sm leading-snug font-medium">{step.title}</p>
            {step.note && (
              <p className="text-muted-foreground mt-0.5 text-xs leading-snug">{step.note}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
