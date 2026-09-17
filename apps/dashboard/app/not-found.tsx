import Link from "next/link";

export default function NotFound() {
	return (
		<main className="error-screen">
			<p className="eyebrow">404</p>
			<h1>View not found</h1>
			<p className="muted">The requested operational view does not exist.</p>
			<Link className="button primary" href="/overview">Go to overview</Link>
		</main>
	);
}
