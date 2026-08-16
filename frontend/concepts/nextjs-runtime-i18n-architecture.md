# Question 94

What is the most efficient architectural approach to internationalize (i18n) a Next.js app supporting instant, dynamic runtime translations?

## Summary
**The Problem:** Hardcoding UI strings inside components makes adding languages unmaintainable, and loading every language's translation bundle up front bloats the initial JavaScript payload for users who only need one locale.

**The Solution:** Separate content from logic using translation keys and per-locale dictionaries, detect the active locale from the route (`/[locale]/...`), dynamically import and cache only the dictionary in use, expose it through React Context, and render the first paint on the server for SEO — so switching languages updates the UI instantly without a full page reload.

## Why it matters
Internationalization done well is invisible: components never know which language is active, they only ask for a key. Loading all locales eagerly (e.g., 5 languages × 5 MB) multiplies bundle size for no benefit, since a given user only ever needs one. Route-based locale detection also keeps localized pages crawlable and cacheable, which matters for SEO in a way that a language toggle stored only in client state does not.

## Key Concepts
- **Translation keys:** components call `t("welcome")` instead of embedding literal text, so no component changes when a language is added.
- **Per-locale dictionaries:** JSON files with identical keys and translated values, organized into namespaces (`common.json`, `checkout.json`) so pages load only what they need.
- **Dynamic import + cache:** only the active locale's dictionary is fetched; once loaded, it's kept in memory so switching back is instant.
- **Server vs. Client Components:** Server Components resolve the locale and render localized HTML for SEO/first paint; Client Components re-render from Context when the user switches language at runtime.
- **Locale-aware formatting:** dates, numbers, and currency use the `Intl` API rather than hardcoded formats, and RTL languages flip `dir="rtl"` at the layout level.

## How to do it
1. Add a `[locale]` dynamic segment (`app/[locale]/...`) so URLs like `/en`, `/fr`, `/de` map directly to a locale.
2. Store all UI strings in per-locale, namespaced JSON dictionaries (`messages/en/common.json`, `messages/fr/common.json`, …) with identical keys across locales.
3. In the Server Component for a route, read the locale from params and dynamically `import()` only the dictionary(ies) that page needs.
4. Provide the loaded dictionary and current locale through a React Context so Client Components can call `t(key)` without prop drilling.
5. On language switch, update the route/locale, dynamically load the new dictionary if not already cached, and update Context — components re-render with the new strings, no full page reload.
6. Cache dictionaries in memory after first load so switching back to a previously used language is instant.
7. Define a fallback locale (usually the default) so a missing key in one dictionary doesn't render blank.
8. Use `Intl.DateTimeFormat`/`Intl.NumberFormat`/`Intl.RelativeTimeFormat` for locale-specific formatting instead of manual string formatting.

## Example
```tsx
// app/[locale]/layout.tsx (Server Component)
export default async function LocaleLayout({ children, params: { locale } }) {
  const dict = await import(`@/messages/${locale}/common.json`).then(m => m.default);
  return (
    <html lang={locale} dir={rtlLocales.includes(locale) ? "rtl" : "ltr"}>
      <body>
        <TranslationProvider locale={locale} dict={dict}>
          {children}
        </TranslationProvider>
      </body>
    </html>
  );
}

// Client-side usage
function LoginButton() {
  const { t } = useTranslation(); // reads from Context
  return <button>{t("login")}</button>;
}
```

## Additional details
- Namespacing translations by page/feature (rather than one giant file) keeps per-route bundles small as the app scales to tens of thousands of strings.
- Missing-translation fallback should be silent to the user (fall back to default locale) but logged, so gaps get fixed before they ship.
- RTL support is a layout concern, not just a text-direction flag — icons, spacing, and navigation order need to adapt too.
- Keep locale switching URL-driven (not just client state) so shared links and search engines see the correct localized page.

## Why this helps
- Users only download the dictionary for their own language, minimizing initial JS payload.
- Components stay identical across all locales — no per-language branching in application code.
- Server-rendered localized HTML improves SEO and first-paint performance.
- Runtime language switching feels instant because dictionaries are cached after first load.

## Trade-offs
| Aspect | Impact | Description |
|---|---|---|
| Route-based locale (`[locale]`) | Positive | SEO-friendly, shareable URLs, but requires locale-aware routing/middleware. |
| Dynamic dictionary import | Positive | Minimizes bundle size, but adds a loading state on first switch to an uncached locale. |
| Namespaced translations | Positive | Keeps per-page payload small, but adds bookkeeping to keep keys in sync across files. |
| Server Component rendering | Positive | Better SEO/initial paint, but ties locale resolution to the server request. |
| Fallback locale | Necessary cost | Prevents blank UI on missing keys, but can mask incomplete translation work if not logged. |

## References
- [Next.js App Router: Internationalization](https://nextjs.org/docs/app/building-your-application/routing/internationalization)
- [MDN: Intl API](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl)
- [next-intl documentation](https://next-intl.dev/)
