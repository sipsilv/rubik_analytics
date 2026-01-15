'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Modal } from '@/components/ui/Modal'
import { adminAPI } from '@/lib/api'
import { ArrowLeft, Eye } from 'lucide-react'
import Link from 'next/link'
import { RefreshButton } from '@/components/ui/RefreshButton'

export default function ProcessorDetailsPage() {
    const [activeTab, setActiveTab] = useState('extraction')
    const [tableData, setTableData] = useState<any[]>([])
    const [dataLoading, setDataLoading] = useState(false)
    const [selectedContent, setSelectedContent] = useState<string | null>(null)

    const formatToIST = (dateString: string) => {
        if (!dateString) return '-'

        // Manual Parsing to ignore Timezone shifts completely
        // Backend text is already in IST (e.g. "2026-01-15 14:52:15")
        // We just want to format "2026-01-15 14:52" -> "15 Jan, 02:52 PM"

        try {
            const datePart = dateString.split('.')[0] // Remove microseconds
            const [y, m, d, h, min] = datePart.split(/[-T :]/)

            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            const monthName = months[parseInt(m) - 1]

            let hour = parseInt(h)
            const ampm = hour >= 12 ? 'PM' : 'AM'
            hour = hour % 12
            hour = hour ? hour : 12 // the hour '0' should be '12'

            const minStr = min.toString().padStart(2, '0')

            return `${d} ${monthName}, ${hour.toString().padStart(2, '0')}:${minStr} ${ampm}`
        } catch (e) {
            return dateString
        }
    }

    const loadData = async (type: string) => {
        try {
            setDataLoading(true)
            const res = await adminAPI.getProcessorData(type)
            setTableData(res || [])
        } catch (e) {
            console.error('Failed to load data', e)
        } finally {
            setDataLoading(false)
        }
    }

    useEffect(() => {
        loadData(activeTab)
    }, [activeTab])

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <Link href="/admin/processors" className="p-2 hover:bg-[#1f2a44] rounded-lg transition-colors text-text-secondary hover:text-text-primary">
                    <ArrowLeft className="w-5 h-5" />
                </Link>
                <div>
                    <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
                        Processor Data
                    </h1>
                    <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
                        View detailed records from the processing pipeline
                    </p>
                </div>
                <RefreshButton
                    className="ml-auto"
                    onClick={async () => await loadData(activeTab)}
                    disabled={dataLoading}
                />
            </div>

            {/* Data Tables Section */}
            <div className="space-y-4">
                <div className="flex border-b border-[#1f2a44] gap-6">
                    <button
                        onClick={() => setActiveTab('extraction')}
                        className={`pb-3 text-sm font-semibold transition-colors ${activeTab === 'extraction' ? 'text-primary border-b-2 border-primary' : 'text-text-secondary hover:text-text-primary'}`}
                    >
                        1. Extraction Table
                    </button>
                    <button
                        onClick={() => setActiveTab('scoring')}
                        className={`pb-3 text-sm font-semibold transition-colors ${activeTab === 'scoring' ? 'text-primary border-b-2 border-primary' : 'text-text-secondary hover:text-text-primary'}`}
                    >
                        2. Scoring Table
                    </button>
                    <button
                        onClick={() => setActiveTab('enrichment')}
                        className={`pb-3 text-sm font-semibold transition-colors ${activeTab === 'enrichment' ? 'text-primary border-b-2 border-primary' : 'text-text-secondary hover:text-text-primary'}`}
                    >
                        3. AI Enrichment Table
                    </button>
                </div>

                <Card className="bg-[#121b2f] border-[#1f2a44] overflow-hidden p-0">
                    {dataLoading ? (
                        <div className="p-8 text-center text-text-secondary">Loading Data...</div>
                    ) : (
                        <Table>
                            <TableHeader>
                                {activeTab === 'extraction' ? (
                                    <>
                                        <TableHeaderCell>Raw ID</TableHeaderCell>
                                        <TableHeaderCell>Received At</TableHeaderCell>
                                        <TableHeaderCell>Msg ID</TableHeaderCell>
                                        <TableHeaderCell>Source</TableHeaderCell>
                                        <TableHeaderCell>Content (Preview)</TableHeaderCell>
                                        <TableHeaderCell>Links</TableHeaderCell>
                                        <TableHeaderCell>OCR</TableHeaderCell>
                                        <TableHeaderCell>Status</TableHeaderCell>
                                    </>
                                ) : activeTab === 'scoring' ? (
                                    <>
                                        <TableHeaderCell>Score ID</TableHeaderCell>
                                        <TableHeaderCell>Raw ID</TableHeaderCell>
                                        <TableHeaderCell>Received At</TableHeaderCell>
                                        <TableHeaderCell>Source</TableHeaderCell>
                                        <TableHeaderCell>Content</TableHeaderCell>
                                        <TableHeaderCell numeric>Final</TableHeaderCell>
                                        <TableHeaderCell numeric>Structure</TableHeaderCell>
                                        <TableHeaderCell numeric>Keyword</TableHeaderCell>
                                        <TableHeaderCell numeric>Source</TableHeaderCell>
                                        <TableHeaderCell numeric>Content</TableHeaderCell>
                                        <TableHeaderCell>Decision</TableHeaderCell>
                                    </>
                                ) : (
                                    <>
                                        <TableHeaderCell>Final ID</TableHeaderCell>
                                        <TableHeaderCell>Processed At</TableHeaderCell>
                                        <TableHeaderCell>Headline</TableHeaderCell>
                                        <TableHeaderCell>Category</TableHeaderCell>
                                        <TableHeaderCell>Sentiment</TableHeaderCell>
                                        <TableHeaderCell numeric>Impact</TableHeaderCell>
                                        <TableHeaderCell>Model</TableHeaderCell>
                                        <TableHeaderCell numeric>Latency (ms)</TableHeaderCell>
                                    </>
                                )}
                            </TableHeader>
                            <TableBody>
                                {tableData.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={activeTab === 'extraction' ? 8 : activeTab === 'scoring' ? 11 : 8} className="text-center text-text-secondary">No recent data found.</TableCell>
                                    </TableRow>
                                ) : tableData.map((row: any, idx) => (
                                    <TableRow key={idx} index={idx}>
                                        {activeTab === 'extraction' ? (
                                            <>
                                                <TableCell className="font-mono text-xs text-text-secondary">{row.raw_id}</TableCell>
                                                <TableCell className="text-text-secondary text-xs">{formatToIST(row.received_at)}</TableCell>
                                                <TableCell className="font-mono text-xs text-text-secondary">{row.telegram_msg_id}</TableCell>
                                                <TableCell className="text-primary">{row.source_handle}</TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <button
                                                            onClick={() => setSelectedContent(row.normalized_text)}
                                                            className="p-1 hover:bg-[#1f2a44] rounded text-primary transition-colors"
                                                            title="View Full Content"
                                                        >
                                                            <Eye className="w-4 h-4" />
                                                        </button>
                                                        <span className="max-w-[200px] truncate text-text-secondary" title={row.normalized_text}>
                                                            {row.normalized_text}
                                                        </span>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-xs">
                                                    {row.link_text ? <span className="text-primary truncate max-w-[100px] block" title={row.link_text}>Yes</span> : <span className="text-text-secondary/50">No</span>}
                                                </TableCell>
                                                <TableCell className="text-xs">
                                                    {row.image_ocr_text ? <span className="text-primary truncate max-w-[100px] block" title={row.image_ocr_text}>Yes</span> : <span className="text-text-secondary/50">No</span>}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex gap-1">
                                                        {row.is_duplicate && (
                                                            <div className="flex items-center gap-1">
                                                                <span className="text-[10px] bg-error/10 text-error px-1.5 py-0.5 rounded">DUP</span>
                                                                {row.duplicate_of && <span className="text-[10px] text-text-secondary">of #{row.duplicate_of}</span>}
                                                            </div>
                                                        )}
                                                        {row.is_scored && <span className="text-[10px] bg-success/10 text-success px-1.5 py-0.5 rounded">SCORED</span>}
                                                        {!row.is_duplicate && !row.is_scored && <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">NEW</span>}
                                                    </div>
                                                </TableCell>
                                            </>
                                        ) : activeTab === 'scoring' ? (
                                            <>
                                                <TableCell className="font-mono text-xs text-text-secondary">{row.score_id}</TableCell>
                                                <TableCell className="font-mono text-xs text-text-secondary">{row.raw_id}</TableCell>
                                                <TableCell className="text-text-secondary text-xs">
                                                    <span title={`Scored At: ${formatToIST(row.scored_at)}`}>{formatToIST(row.received_at)}</span>
                                                </TableCell>
                                                <TableCell className="text-primary">{row.source}</TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <button
                                                            onClick={() => setSelectedContent(row.combined_text)}
                                                            className="p-1 hover:bg-[#1f2a44] rounded text-primary transition-colors"
                                                            title="View Full Content"
                                                        >
                                                            <Eye className="w-4 h-4" />
                                                        </button>
                                                        <span className="max-w-[150px] truncate text-text-secondary" title={row.combined_text}>
                                                            {row.combined_text}
                                                        </span>
                                                    </div>
                                                </TableCell>
                                                <TableCell numeric className="font-bold text-primary">{row.final_score}</TableCell>
                                                <TableCell numeric className="text-text-secondary text-xs">{row.structural_score}</TableCell>
                                                <TableCell numeric className="text-text-secondary text-xs">{row.keyword_score}</TableCell>
                                                <TableCell numeric className="text-text-secondary text-xs">{row.source_score}</TableCell>
                                                <TableCell numeric className="text-text-secondary text-xs">{row.content_score}</TableCell>
                                                <TableCell>
                                                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${row.decision === 'PASS' ? 'bg-success/10 text-success' : 'bg-error/10 text-error'}`}>
                                                        {row.decision}
                                                    </span>
                                                </TableCell>
                                            </>
                                        ) : (
                                            <>
                                                <TableCell className="font-mono text-xs text-text-secondary">{row.final_id}</TableCell>
                                                <TableCell className="text-text-secondary text-xs">{formatToIST(row.processed_at)}</TableCell>
                                                <TableCell className="font-medium text-text-primary">{row.headline}</TableCell>
                                                <TableCell>
                                                    <span className="text-xs px-2 py-0.5 bg-secondary/10 rounded-full text-secondary">
                                                        {row.category}
                                                    </span>
                                                </TableCell>
                                                <TableCell>
                                                    <span className={`text-xs font-bold ${row.sentiment === 'Positive' ? 'text-success' :
                                                            row.sentiment === 'Negative' ? 'text-error' : 'text-warning'
                                                        }`}>
                                                        {row.sentiment}
                                                    </span>
                                                </TableCell>
                                                <TableCell numeric className="font-bold text-text-primary">{row.impact_score}</TableCell>
                                                <TableCell className="text-xs text-text-secondary">{row.ai_model}</TableCell>
                                                <TableCell numeric className="text-xs text-text-secondary font-mono">{row.latency}</TableCell>
                                            </>
                                        )}
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </Card>
            </div>

            <Modal
                isOpen={!!selectedContent}
                onClose={() => setSelectedContent(null)}
                title="Message Content"
            >
                <div className="whitespace-pre-wrap text-text-secondary font-mono text-sm max-h-[60vh] overflow-y-auto p-2 bg-[#1f2a44]/20 rounded">
                    {selectedContent || "No content available."}
                </div>
            </Modal>
        </div>
    )
}
