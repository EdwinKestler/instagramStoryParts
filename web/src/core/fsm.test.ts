import { describe, expect, it } from "vitest";

import { InvalidStateTransition, SplitStateMachine } from "./fsm";

describe("SplitStateMachine", () => {
  it("records the complete successful lifecycle", () => {
    const machine = new SplitStateMachine();

    for (const state of [
      "validating",
      "loading",
      "probing",
      "planning",
      "exporting",
      "completed"
    ] as const) {
      machine.transitionTo(state);
    }

    expect(machine.state).toBe("completed");
    expect(machine.history.map(({ current }) => current)).toEqual([
      "validating",
      "loading",
      "probing",
      "planning",
      "exporting",
      "completed"
    ]);
  });

  it("rejects an illegal transition without mutating state", () => {
    const machine = new SplitStateMachine();

    expect(() => machine.transitionTo("exporting")).toThrow(InvalidStateTransition);
    expect(machine.state).toBe("created");
    expect(machine.history).toHaveLength(0);
  });

  it("makes failure and cancellation terminal", () => {
    const failed = new SplitStateMachine();
    failed.fail();
    failed.fail();

    const cancelled = new SplitStateMachine();
    cancelled.cancel();
    cancelled.cancel();

    expect(failed.state).toBe("failed");
    expect(failed.history).toHaveLength(1);
    expect(cancelled.state).toBe("cancelled");
    expect(cancelled.history).toHaveLength(1);
  });
});
