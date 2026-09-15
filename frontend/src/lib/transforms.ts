import { useQuery } from '@tanstack/react-query'
import type { ArtefactType } from './api'

export interface TransformRow {
  transform_id: string
  created_at: string
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'
  output_types: ArtefactType[]
  job_count: number
  has_verification: boolean
  verification_ok: boolean | null
  conflicts: number
}

export function useRecentTransforms() {
  return useQuery({
    queryKey: ['transforms'],
    queryFn: async (): Promise<TransformRow[]> => {
      const response = await fetch('/transforms?limit=25')
      if (!response.ok)
        throw new Error(
          'Recent transforms are unavailable. Check that the local engine is running.',
        )
      return response.json()
    },
    refetchInterval: 20_000,
  })
}
