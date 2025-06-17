import { Server } from 'lucide-react'

const Baseline = () => {
  console.log('Baseline page rendering') // Debug log
  
  return (
    <div style={{ padding: '20px', color: 'white' }}>
      <h1 style={{ fontSize: '2rem', marginBottom: '1rem' }}>System Baseline</h1>
      <p style={{ color: '#a1a1aa', marginBottom: '2rem' }}>Monitor system baseline and detect anomalies</p>
      
      <div style={{ backgroundColor: '#27272a', padding: '1.5rem', borderRadius: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <Server style={{ width: '2rem', height: '2rem', color: '#60a5fa', marginRight: '1rem' }} />
          <div>
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600' }}>Processes</h3>
            <p style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#60a5fa' }}>156</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Baseline
