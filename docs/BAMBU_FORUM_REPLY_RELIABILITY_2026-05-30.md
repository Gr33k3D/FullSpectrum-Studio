# Forum Reply Draft

Hi Mike,

Thank you for testing and for calling this out. I found a real app-side
reliability bug: the macOS wrapper was reading the engine log stream while the
converter ran, but it waited until process exit to read the final JSON result.
For bigger painted files that JSON can be large enough to block the Python
process before it exits, which looks like a frozen conversion.

I have reworked the next build so stdout and stderr are both drained while the
engine runs, added a visible Cancel button, added long-running heartbeat status,
and replaced the useless `none` failure with the actual Python error/traceback.
Failed conversions now write a local debug log and the app has a Copy Error
Report button. I also fixed the dark-mode picker/button readability problems
and the custom JSON palette start path.

One important clarification: FullSpectrum reduces/remaps existing Bambu paint
states. It does not repaint or smooth a model that already has noisy/bad paint
regions, so some complex painted files can still be difficult. The goal of this
fix is that they either finish or fail with useful diagnostics instead of
hanging or hiding the real error.

If you can retry with the next package and paste the copied error report for
any failing `.3mf`, I can use that to keep narrowing the hard cases.
