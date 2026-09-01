export const splitStates = [
  "created",
  "validating",
  "loading",
  "probing",
  "planning",
  "exporting",
  "completed",
  "failed",
  "cancelled"
] as const;

export type SplitState = (typeof splitStates)[number];

export interface StateTransition {
  readonly previous: SplitState;
  readonly current: SplitState;
  readonly occurredAt: number;
}

export class InvalidStateTransition extends Error {}

type TransitionListener = (transition: StateTransition) => void;

const allowedTransitions: Readonly<Record<SplitState, ReadonlySet<SplitState>>> = {
  created: new Set(["validating", "failed", "cancelled"]),
  validating: new Set(["loading", "failed", "cancelled"]),
  loading: new Set(["probing", "failed", "cancelled"]),
  probing: new Set(["planning", "failed", "cancelled"]),
  planning: new Set(["exporting", "failed", "cancelled"]),
  exporting: new Set(["completed", "failed", "cancelled"]),
  completed: new Set(),
  failed: new Set(),
  cancelled: new Set()
};

export class SplitStateMachine {
  #state: SplitState = "created";
  readonly #history: StateTransition[] = [];

  constructor(private readonly listener?: TransitionListener) {}

  get state(): SplitState {
    return this.#state;
  }

  get history(): readonly StateTransition[] {
    return [...this.#history];
  }

  transitionTo(target: SplitState): StateTransition {
    if (!allowedTransitions[this.#state].has(target)) {
      throw new InvalidStateTransition(
        `Cannot transition split job from ${this.#state} to ${target}.`
      );
    }
    const transition = {
      previous: this.#state,
      current: target,
      occurredAt: performance.now()
    } satisfies StateTransition;
    this.#state = target;
    this.#history.push(transition);
    this.listener?.(transition);
    return transition;
  }

  fail(): void {
    if (!this.isTerminal()) this.transitionTo("failed");
  }

  cancel(): void {
    if (!this.isTerminal()) this.transitionTo("cancelled");
  }

  private isTerminal(): boolean {
    return ["completed", "failed", "cancelled"].includes(this.#state);
  }
}
