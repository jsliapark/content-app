import type {
  BrandMutationResult,
  BrandOverviewResponse,
  BrandProfile,
  BrandSamplesResponse,
} from '../types/brand'

export async function getBrandOverview(): Promise<BrandOverviewResponse> {
  const res = await fetch('/api/brand/overview')
  if (!res.ok) {
    throw new Error(`Failed to load brand overview: ${res.status}`)
  }
  return res.json() as Promise<BrandOverviewResponse>
}

export async function getProfile(): Promise<BrandProfile> {
  const res = await fetch('/api/brand/profile')
  if (!res.ok) {
    throw new Error(`Failed to load profile: ${res.status}`)
  }
  return res.json() as Promise<BrandProfile>
}

export async function listSamples(): Promise<BrandSamplesResponse> {
  const res = await fetch('/api/brand/samples')
  if (!res.ok) {
    throw new Error(`Failed to load samples: ${res.status}`)
  }
  return res.json() as Promise<BrandSamplesResponse>
}

export async function deleteSamples(
  body: { all: true } | { sample_ids: string[] },
): Promise<BrandMutationResult> {
  const payload =
    'all' in body && body.all === true
      ? { all: true }
      : { sample_ids: (body as { sample_ids: string[] }).sample_ids }
  const res = await fetch('/api/brand/samples/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Delete samples failed: ${res.status} ${text}`)
  }
  return res.json() as Promise<BrandMutationResult>
}

export async function ingestSamples(content: string): Promise<BrandMutationResult> {
  const res = await fetch('/api/brand/samples', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Ingest failed: ${res.status} ${text}`)
  }
  return res.json() as Promise<BrandMutationResult>
}

export async function setGuidelines(guidelines: string): Promise<BrandMutationResult> {
  const res = await fetch('/api/brand/guidelines', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ guidelines }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Save guidelines failed: ${res.status} ${text}`)
  }
  return res.json() as Promise<BrandMutationResult>
}
