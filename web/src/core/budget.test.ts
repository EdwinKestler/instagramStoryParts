import { describe, expect, it } from "vitest";

import { estimateVercelProCost, vercelBudgetPolicy } from "./budget";

describe("Vercel budget policy", () => {
  it("keeps the recommended WASM cold-load cap within included transfer", () => {
    const estimate = estimateVercelProCost({
      monthlyColdLoads: vercelBudgetPolicy.wasmColdLoadsPerDay * 30,
      deliveredMegabytesPerLoad: 31,
      requestsPerLoad: 8
    });

    expect(estimate.transferGigabytes).toBe(930);
    expect(estimate.transferOverageUsd).toBe(0);
    expect(estimate.estimatedTotalUsd).toBe(20);
    expect(estimate.estimatedTotalUsd).toBeLessThan(
      vercelBudgetPolicy.operationalMonthlyTargetUsd
    );
  });

  it("reserves twenty dollars below the absolute ceiling", () => {
    expect(
      vercelBudgetPolicy.absoluteMonthlyCeilingUsd -
        vercelBudgetPolicy.operationalMonthlyTargetUsd
    ).toBe(20);
    expect(vercelBudgetPolicy.meteredSpendPauseUsd + 20).toBe(
      vercelBudgetPolicy.operationalMonthlyTargetUsd
    );
  });

  it("prices overages at the highest published regional rate", () => {
    const estimate = estimateVercelProCost({
      monthlyColdLoads: 1_000_000,
      deliveredMegabytesPerLoad: 2,
      requestsPerLoad: 20
    });

    expect(estimate.transferOverageUsd).toBe(350);
    expect(estimate.requestOverageUsd).toBe(32);
    expect(estimate.estimatedTotalUsd).toBe(402);
  });
});
