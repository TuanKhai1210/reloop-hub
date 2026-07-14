import { useState } from 'react'
import { ApiError } from '../api/client'

const LoginPage = ({ onBack, onLogin }) => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await onLogin(email, password)
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Unable to reach the ReLoop API. Check the backend URL and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <span className="eyebrow">Protected staff workspace</span>
        <h1 id="login-title">Sign in to ReLoop operations</h1>
        <p>Use an active backend account with Admin, Operator or Recycler access. Authorization is checked by FastAPI for every protected request.</p>
        <form onSubmit={submit}>
          <label>
            Email
            <input autoComplete="username" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            Password
            <input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength="8" />
          </label>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="button button-primary button-full" type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in securely'}
          </button>
          <button className="button button-text button-full" type="button" onClick={onBack}>Back to project overview</button>
        </form>
      </section>
    </main>
  )
}

export default LoginPage
