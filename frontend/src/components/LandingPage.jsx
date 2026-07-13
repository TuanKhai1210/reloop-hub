import background from '../assets/background.jpg'
import educationIcon from '../assets/education.png'
import recycleIcon from '../assets/recycle-sign.png'
import transportIcon from '../assets/transport.png'

const flow = [
  {
    step: '01',
    title: 'Guide the return',
    description: 'Students return one clean PET or HDPE bottle at a high-traffic campus canteen.',
  },
  {
    step: '02',
    title: 'Verify before reward',
    description: 'The Hub checks material signals, cleanliness and weight before Green Points are issued.',
  },
  {
    step: '03',
    title: 'Aggregate by material',
    description: 'Accepted bottles enter separate PET and HDPE batches with item-level trace records.',
  },
  {
    step: '04',
    title: 'Collect when ready',
    description: 'Fill level triggers a route only when the Hub has enough verified material to collect.',
  },
]

const valueCards = [
  { icon: educationIcon, title: 'Behavior loop', text: 'Immediate feedback and canteen-linked Green Points make the return action easy to repeat.' },
  { icon: recycleIcon, title: 'Verified feedstock', text: 'PET and HDPE are separated before downstream sorting, preserving more material value.' },
  { icon: transportIcon, title: 'Data-led pickup', text: 'Operators see readiness, route efficiency and end-to-end batch movement in one place.' },
]

const LandingPage = ({ demoMode, onDashboard }) => (
  <main>
    <section className="hero" style={{ '--hero-image': `url(${background})` }}>
      <div className="hero-overlay" />
      <div className="hero-content">
        <span className="eyebrow">Campus pilot · PET &amp; HDPE · Round 2 prototype</span>
        <h1>Turn every verified bottle return into a cleaner material flow.</h1>
        <p>
          ReLoop Hub connects student behavior, Smart RVM verification, Green Points, pickup readiness and traceability in one reverse-logistics system.
        </p>
        <div className="hero-actions">
          <button className="button button-primary" type="button" onClick={onDashboard}>
            {demoMode ? 'Explore the demo dashboard' : 'Open staff dashboard'}
          </button>
          <a className="button button-secondary" href="#system-flow">See how the loop works</a>
        </div>
        {demoMode && (
          <p className="demo-disclaimer">
            Prototype mode uses labelled sample data for interaction testing. It does not represent measured pilot impact.
          </p>
        )}
      </div>
    </section>

    <section className="section" aria-labelledby="why-reloop">
      <div className="section-heading">
        <span className="eyebrow">The upstream bottleneck</span>
        <h2 id="why-reloop">Plastic loses value before it reaches the recycler.</h2>
        <p>Mixed, dirty, scattered and untraceable bottles create avoidable sorting and collection costs. ReLoop starts by improving the return point.</p>
      </div>
      <div className="value-grid">
        {valueCards.map((card) => (
          <article className="value-card" key={card.title}>
            <img src={card.icon} alt="" />
            <h3>{card.title}</h3>
            <p>{card.text}</p>
          </article>
        ))}
      </div>
    </section>

    <section className="section section-tinted" id="system-flow" aria-labelledby="flow-title">
      <div className="section-heading">
        <span className="eyebrow">One bottle, one auditable journey</span>
        <h2 id="flow-title">From canteen return to recycler receipt.</h2>
      </div>
      <div className="flow-grid">
        {flow.map((item) => (
          <article className="flow-step" key={item.step}>
            <span>{item.step}</span>
            <h3>{item.title}</h3>
            <p>{item.description}</p>
          </article>
        ))}
      </div>
    </section>

    <section className="section pilot-section">
      <div>
        <span className="eyebrow">Validation ladder</span>
        <h2>Campus proves the loop. Communities prove repetition. Retail proves scale.</h2>
      </div>
      <ol className="pilot-list">
        <li><strong>Phase 1</strong><span>University canteen behavior and operating flow</span></li>
        <li><strong>Phase 2</strong><span>Residential repeat behavior and material quality</span></li>
        <li><strong>Phase 3</strong><span>Urban convenience-store network and route scale</span></li>
      </ol>
    </section>

    <footer className="site-footer">
      <strong>ReLoop Hub</strong>
      <span>Verified reverse logistics for PET and HDPE.</span>
    </footer>
  </main>
)

export default LandingPage
