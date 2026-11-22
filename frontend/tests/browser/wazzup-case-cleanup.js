// A failed fixture case must release its held HTTP request before another case
// starts. Keep the original failure if cleanup or its diagnostic also fails.
export async function withWazzupCaseCleanup(run, cleanup, reportFailure) {
  let result
  let failed = false
  let failure
  let cleanupFailed = false
  let cleanupFailure
  try {
    result = await run()
  } catch (error) {
    failed = true
    failure = error
  } finally {
    try {
      await cleanup()
    } catch (error) {
      cleanupFailed = true
      cleanupFailure = error
    }
  }
  if (cleanupFailed) {
    if (!failed) throw cleanupFailure
    try {
      await reportFailure?.(cleanupFailure)
    } catch {
      // Diagnostic failures must not replace the original scenario error.
    }
  }
  if (failed) throw failure
  return result
}
