export default function AnimationsPanel() {
  return (
    <div className="animations-panel">
      <div className="animations-layout">
        <div className="animations-case">
          <div className="shimmer-case-header">
            <span className="shimmer-case-title">Shimmer</span>
            <span className="shimmer-case-tag">CSS only</span>
          </div>
          <div className="shimmer-case">
            <div className="shimmer-card">
              <div className="shimmer-thumb" />
              <div className="shimmer-body">
                <div className="shimmer-line shimmer-line-short" />
                <div className="shimmer-line" />
                <div className="shimmer-line shimmer-line-medium" />
              </div>
            </div>
          </div>
          <p className="shimmer-note">
            Skeleton placeholders use a soft, non-distracting shimmer so the page
            feels intentional while content loads.
          </p>
        </div>

        <div className="animations-tip">
          <div className="tip-head">
            <span className="tip-title">Why this matters</span>
            <span className="tip-tag">Motion discipline</span>
          </div>
          <p className="tip-body">
            Every transition in the interface has a role: confirm an action, guide
            attention, or reduce the feeling of wait time. None of them are there
            just to be decorative.
          </p>
        </div>
      </div>
    </div>
  );
}