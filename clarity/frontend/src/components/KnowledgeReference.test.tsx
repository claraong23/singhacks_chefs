import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createKnowledgeDocument, getKnowledgeDocuments, knowledgeDocumentAction, searchKnowledge } from '../api'
import { KnowledgeLibrary, KnowledgeReferencePanel } from './KnowledgeReference'
import type { KnowledgeDocument } from '../types'

vi.mock('../api', () => ({ createKnowledgeDocument: vi.fn(), getKnowledgeDocuments: vi.fn(), knowledgeDocumentAction: vi.fn(), searchKnowledge: vi.fn() }))

const result = { citation: { document_id: 'KN-COLLATERAL-001', version: 1, title: 'Collateral reference', effective_date: '2026-08-26', source_refs: ['clarity/docs/METHOD.md'] }, category: 'collateral_liquidity', tags: ['collateral', 'lau'], excerpt: 'Synthetic internal reference for a collateral conversation.', matched_terms: ['collateral'], matched_fields: ['title', 'tags'], score: 19 }
const document: KnowledgeDocument = { id: 'KN-COLLATERAL-001', title: 'Collateral reference', category: 'collateral_liquidity', tags: ['collateral', 'lau'], owner: 'Credit', current_version: 1, approved_version: 1, version: { version: 1, status: 'approved', body: 'Synthetic reference.', source_refs: ['clarity/docs/METHOD.md'], effective_date: '2026-08-26', created_at: '2026-08-26', created_by: 'system', rationale: 'Seed' } }

describe('Knowledge reference library', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(getKnowledgeDocuments).mockResolvedValue({ documents: [document] }); vi.mocked(searchKnowledge).mockResolvedValue({ results: [result] }) })
  afterEach(cleanup)

  it('shows cited approved results from a contextual safe shortcut', async () => {
    const user = userEvent.setup()
    render(<KnowledgeReferencePanel role="rm" category="collateral_liquidity" location="action_review" />)
    await user.click(screen.getByRole('button', { name: 'Search reference' }))
    expect(await screen.findByText('Collateral reference')).toBeInTheDocument()
    expect(screen.getByText('Synthetic internal reference for a collateral conversation.')).toBeInTheDocument()
    expect(searchKnowledge).toHaveBeenCalledWith(expect.objectContaining({ category: 'collateral_liquidity', location: 'action_review' }))
  })

  it('lets Operations create drafts while all roles can search approved documents', async () => {
    vi.mocked(createKnowledgeDocument).mockResolvedValue({ document })
    vi.mocked(getKnowledgeDocuments).mockResolvedValue({ documents: [] })
    const user = userEvent.setup()
    render(<KnowledgeLibrary role="operations" />)
    await screen.findByText('Document register')
    await user.type(screen.getByPlaceholderText('Title'), 'Synthetic evidence guide')
    await user.type(screen.getByPlaceholderText('Synthetic approved-reference wording'), 'Synthetic prototype reference body.')
    await user.type(screen.getByPlaceholderText('Why this draft or revision is needed'), 'Add a controlled guide.')
    await user.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(createKnowledgeDocument).toHaveBeenCalled())
    expect(knowledgeDocumentAction).not.toHaveBeenCalled()
  })
})
