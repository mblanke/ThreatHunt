import React from 'react';
import { useAuth } from '../context/AuthContext';

const Dashboard: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>VelociCompanion Dashboard</h1>
        <button onClick={logout} style={styles.logoutButton}>
          Logout
        </button>
      </div>
      
      <div style={styles.content}>
        <div style={styles.card}>
          <h2>Welcome, {user?.username}!</h2>
          <p><strong>Role:</strong> {user?.role}</p>
          <p><strong>Tenant ID:</strong> {user?.tenant_id}</p>
          <p><strong>Status:</strong> {user?.is_active ? 'Active' : 'Inactive'}</p>
        </div>
        
        <div style={styles.card}>
          <h3>Getting Started</h3>
          <p>Your authentication system is now set up and working!</p>
          <ul>
            <li>✓ JWT authentication</li>
            <li>✓ Multi-tenancy support</li>
            <li>✓ Role-based access control</li>
            <li>✓ Protected routes</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: 'white',
    padding: '20px 40px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    margin: 0,
    fontSize: '24px',
    color: '#333',
  },
  logoutButton: {
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: '500',
    color: 'white',
    backgroundColor: '#dc3545',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  content: {
    padding: '40px',
    maxWidth: '1200px',
    margin: '0 auto',
  },
  card: {
    backgroundColor: 'white',
    padding: '30px',
    borderRadius: '8px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    marginBottom: '20px',
  },
};

export default Dashboard;
