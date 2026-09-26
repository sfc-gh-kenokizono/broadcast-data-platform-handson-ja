import { describe, expect, it } from "vitest"
import { aggregateSql, parseFilters, shiftPeriod, validatePredictionRows } from "@/lib/broadcast"

describe("broadcast query validation", () => {
  it("accepts only valid dates and station identifiers", () => {
    const filters = parseFilters(new URLSearchParams("from=2026-05-01&to=2026-05-07&networks=NW01,NW02"))
    expect(filters.networks).toEqual(["NW01", "NW02"])
    expect(() => parseFilters(new URLSearchParams("from=2026-05-01&to=2026-05-07&networks=NW01,BAD"))).toThrow()
  })

  it("binds filter values instead of interpolating them", () => {
    const filters = parseFilters(new URLSearchParams("from=2026-05-01&to=2026-05-07&networks=NW01,NW02"))
    const query = aggregateSql(["NETWORK_ID"], filters)
    expect(query.sql).toContain("VIEW_DATE BETWEEN ? AND ? AND NETWORK_ID IN (?, ?)")
    expect(query.sql).not.toContain("2026-05-01")
    expect(query.binds).toEqual(["2026-05-01", "2026-05-07", "NW01", "NW02"])
  })

  it("computes the equal-length previous period", () => {
    const filters = parseFilters(new URLSearchParams("from=2026-05-08&to=2026-05-14&networks=NW01"))
    expect(shiftPeriod(filters)).toMatchObject({ from: "2026-05-01", to: "2026-05-07" })
  })
})

describe("prediction snapshot validation", () => {
  it("accepts the expected complete snapshot", () => {
    expect(validatePredictionRows([{
      ROW_COUNT: 20000, DEVICE_COUNT: 20000, INVALID_COUNT: 0,
      THRESHOLD_COUNT: 1, PREDICTION_THRESHOLD: 0.5,
      MODEL_VERSION_COUNT: 1, MODEL_VERSION: "V1", PREDICTED_AT_COUNT: 1,
      DATASET_VERSION_COUNT: 1, DATASET_VERSION: "F1_SIGNAL_V2",
    }])?.modelVersion).toBe("V1")
  })

  it("fails closed for incomplete predictions", () => {
    expect(() => validatePredictionRows([{
      ROW_COUNT: 19999, DEVICE_COUNT: 19999, INVALID_COUNT: 0,
      THRESHOLD_COUNT: 1, PREDICTION_THRESHOLD: 0.5,
      MODEL_VERSION_COUNT: 1, MODEL_VERSION: "V1", PREDICTED_AT_COUNT: 1,
      DATASET_VERSION_COUNT: 1, DATASET_VERSION: "F1_SIGNAL_V2",
    }])).toThrow("20,000端末")
  })
})
