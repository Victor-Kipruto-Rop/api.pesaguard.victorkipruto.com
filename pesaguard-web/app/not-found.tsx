import Link from "next/link";
export default function NotFound(){return <section className="page-hero"><div className="container"><p className="eyebrow">404</p><h1>That page is not in the ledger.</h1><p className="lede">The address may have changed. Let us get you back to the useful stuff.</p><Link className="button button-primary" href="/">Return home</Link></div></section>}
