export interface VercelCostInput {
  readonly monthlyColdLoads: number;
  readonly deliveredMegabytesPerLoad: number;
  readonly requestsPerLoad: number;
}

export interface VercelCostEstimate {
  readonly transferGigabytes: number;
  readonly edgeRequests: number;
  readonly transferOverageUsd: number;
  readonly requestOverageUsd: number;
  readonly estimatedTotalUsd: number;
}

const PRO_BASE_USD = 20;
const INCLUDED_TRANSFER_GB = 1_000;
const INCLUDED_EDGE_REQUESTS = 10_000_000;
// Use the high end of Vercel's published regional price range so estimates do
// not depend on where a request is served.
const TRANSFER_USD_PER_GB = 0.35;
const REQUEST_USD_PER_MILLION = 3.2;

export function estimateVercelProCost(input: VercelCostInput): VercelCostEstimate {
  const transferGigabytes =
    (input.monthlyColdLoads * input.deliveredMegabytesPerLoad) / 1_000;
  const edgeRequests = input.monthlyColdLoads * input.requestsPerLoad;
  const transferOverageUsd =
    Math.max(0, transferGigabytes - INCLUDED_TRANSFER_GB) * TRANSFER_USD_PER_GB;
  const requestOverageUsd =
    (Math.max(0, edgeRequests - INCLUDED_EDGE_REQUESTS) / 1_000_000) *
    REQUEST_USD_PER_MILLION;
  return {
    transferGigabytes,
    edgeRequests,
    transferOverageUsd,
    requestOverageUsd,
    estimatedTotalUsd: PRO_BASE_USD + transferOverageUsd + requestOverageUsd
  };
}

export const vercelBudgetPolicy = Object.freeze({
  absoluteMonthlyCeilingUsd: 100,
  operationalMonthlyTargetUsd: 80,
  meteredSpendPauseUsd: 60,
  leanColdLoadsPerDay: 20_000,
  wasmColdLoadsPerDay: 1_000
});
