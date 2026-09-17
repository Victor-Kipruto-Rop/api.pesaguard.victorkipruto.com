"use client";
export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <section className="page-hero"><div className="container"><p className="eyebrow">Something went wrong</p><h1>We could not load this view.</h1><button className="button button-primary" onClick={() => reset()}>Try again</button></div></section>; }
