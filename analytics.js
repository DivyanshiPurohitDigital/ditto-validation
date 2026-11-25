// Ditto analytics. Off by default. Public visitors are never tracked.
// It runs only when the page address contains ?session=1, which you add for a moderated test session
// after the participant has agreed. Example: https://YOUR-NAME.github.io/ditto-validation/?session=1
//
// To switch it on:
// 1. In PostHog, open Project settings and copy the HTML snippet (it contains your project API key).
// 2. Paste it between the two marker lines below.
// 3. In the pasted posthog.init(...) call, set these options, keeping your own key and api_host:
//      person_profiles: 'identified_only', persistence: 'memory', autocapture: false
//    Check the option names against PostHog's current documentation.
// 4. In PostHog, turn on session replay for the project. Keep input masking on.
// The page sends only counts and flags: brief_started, example_loaded, brief_submitted, results_viewed,
// metrics_viewed, each with is_demo = true. It sends no names, emails or free text.
(function () {
  if (!/[?&]session=1(&|$)/.test(location.search)) return;
  // ===== PASTE THE POSTHOG SNIPPET BELOW THIS LINE =====

  // ===== END OF POSTHOG SNIPPET =====
})();
