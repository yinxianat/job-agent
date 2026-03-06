import { useState, useCallback, useEffect, useRef } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  UploadCloudIcon, FileTextIcon, FolderOpenIcon, BrainCircuitIcon,
  CheckCircleIcon, DownloadIcon, TrashIcon, SparklesIcon, FileSpreadsheetIcon,
  FolderIcon, PencilIcon, EyeIcon, XIcon, PrinterIcon, CopyIcon,
  SaveIcon, CheckIcon,
} from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'
import FolderPicker from '../components/FolderPicker'

// ── Resume Preview Modal ──────────────────────────────────────────────────────
function ResumePreviewModal({
  resume,
  onClose,
  saveFolder,
  onOpenFolderPicker,
}) {
  const contentRef = useRef(null)

  // Local editing state
  const [editText, setEditText]   = useState(resume.tailored_text || '')
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving,  setIsSaving]  = useState(false)
  const [savedType, setSavedType] = useState(null)   // 'pdf' | 'docx' | null

  // Build a default filename from the resume's filename (strip extension)
  const defaultFilename = resume.filename
    ? resume.filename.replace(/\.(pdf|docx|doc)$/i, '')
    : 'tailored_resume'

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // Prevent background scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const handleCopy = () => {
    navigator.clipboard.writeText(editText)
    toast.success('Copied to clipboard!')
  }

  const handlePrint = () => {
    const win = window.open('', '_blank')
    if (!win) return
    win.document.write(`
      <html><head><title>${resume.filename}</title>
      <style>
        body { font-family: 'Times New Roman', serif; font-size: 11pt; line-height: 1.5;
               max-width: 750px; margin: 40px auto; padding: 0 20px; color: #111; }
        pre  { white-space: pre-wrap; font-family: inherit; font-size: inherit; }
      </style></head>
      <body><pre>${editText.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre></body></html>
    `)
    win.document.close()
    win.focus()
    win.print()
  }

  const handleSave = async (format) => {
    if (!saveFolder.trim()) {
      toast.error('Please select a save folder first')
      onOpenFolderPicker()
      return
    }
    setIsSaving(true)
    try {
      const fd = new FormData()
      fd.append('text',          editText)
      fd.append('output_folder', saveFolder)
      fd.append('filename',      defaultFilename)

      await api.post('/api/resume/save-preview', fd)
      setSavedType(format)
      toast.success(`Saved ${format.toUpperCase()} to your folder!`)
      setTimeout(() => setSavedType(null), 3000)
    } catch (err) {
      toast.error(err.message || 'Failed to save file')
    } finally {
      setIsSaving(false)
    }
  }

  // Format plain-text resume into structured HTML sections (read-only view)
  const formatResumeText = (text) => {
    if (!text) return null
    const lines = text.split('\n')
    const elements = []

    // Find name/contact block
    let firstSectionIdx = lines.length
    for (let i = 0; i < lines.length; i++) {
      const s = lines[i].trim()
      if (s.length >= 3 && s === s.toUpperCase() && /[A-Z]/.test(s) && !/[a-z]/.test(s) && s.length <= 60) {
        firstSectionIdx = i
        break
      }
    }

    let nameIdx = -1
    const contactIdxs = new Set()
    for (let i = 0; i < firstSectionIdx; i++) {
      if (!lines[i].trim()) continue
      if (nameIdx === -1) { nameIdx = i }
      else { contactIdxs.add(i) }
    }

    lines.forEach((line, i) => {
      const trimmed = line.trim()

      if (!trimmed) {
        elements.push(<div key={`gap-${i}`} className="h-2" />)
        return
      }

      // Name
      if (i === nameIdx) {
        elements.push(
          <div key={`name-${i}`} className="text-center mb-1">
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">{trimmed}</h1>
            <hr className="border-t-2 border-blue-800 mt-2 mb-0" />
          </div>
        )
        return
      }

      // Contact block
      if (contactIdxs.has(i)) {
        elements.push(
          <p key={`contact-${i}`} className="text-xs text-center text-gray-500 leading-snug">{trimmed}</p>
        )
        return
      }

      // ALL-CAPS section header
      const isHeader = trimmed.length >= 3 && trimmed === trimmed.toUpperCase() &&
                       /[A-Z]/.test(trimmed) && !/[a-z]/.test(trimmed) && trimmed.length <= 60
      if (isHeader) {
        elements.push(
          <div key={`h-${i}`} className="mt-5 mb-1">
            <h3 className="text-xs font-bold tracking-widest text-slate-700 uppercase border-b border-gray-300 pb-1">
              {trimmed}
            </h3>
          </div>
        )
        return
      }

      // Bullet point
      if (trimmed.startsWith('•') || trimmed.startsWith('-') || trimmed.startsWith('*')) {
        const bulletText = trimmed.replace(/^[•\-*]\s*/, '')
        elements.push(
          <div key={`b-${i}`} className="flex gap-2 text-sm text-gray-800 leading-relaxed pl-1">
            <span className="text-gray-400 shrink-0 mt-0.5">•</span>
            <span>{bulletText}</span>
          </div>
        )
        return
      }

      // Regular line
      elements.push(
        <p key={`l-${i}`} className="text-sm text-gray-800 leading-relaxed">{trimmed}</p>
      )
    })

    return elements
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-brand-100 flex items-center justify-center shrink-0">
              <FileTextIcon className="w-4 h-4 text-brand-600" />
            </div>
            <div className="min-w-0">
              <p className="font-semibold text-gray-900 text-sm truncate">{resume.filename}</p>
              {resume.job_url && (
                <a href={resume.job_url} target="_blank" rel="noopener noreferrer"
                  className="text-xs text-brand-500 hover:underline truncate block">{resume.job_url}</a>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 ml-4">
            {/* Edit / Done toggle */}
            <button
              onClick={() => setIsEditing((v) => !v)}
              title={isEditing ? 'Switch to formatted view' : 'Edit text'}
              className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors
                ${isEditing
                  ? 'bg-brand-100 text-brand-700 hover:bg-brand-200'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {isEditing
                ? <><EyeIcon className="w-3.5 h-3.5" /> Preview</>
                : <><PencilIcon className="w-3.5 h-3.5" /> Edit</>
              }
            </button>

            <button onClick={handleCopy} title="Copy text"
              className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors">
              <CopyIcon className="w-4 h-4" />
            </button>
            <button onClick={handlePrint} title="Print / Save as PDF"
              className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors">
              <PrinterIcon className="w-4 h-4" />
            </button>

            {/* Original download buttons (from tailor endpoint) */}
            {resume.pdf_path && (
              <a href={`/api/resume/download?path=${encodeURIComponent(resume.pdf_path)}`}
                className="btn-primary text-xs py-1.5 px-3 gap-1">
                <DownloadIcon className="w-3 h-3" /> PDF
              </a>
            )}
            {resume.docx_path && (
              <a href={`/api/resume/download?path=${encodeURIComponent(resume.docx_path)}`}
                className="btn-secondary text-xs py-1.5 px-3 gap-1">
                <DownloadIcon className="w-3 h-3" /> DOCX
              </a>
            )}

            <button onClick={onClose}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors ml-1">
              <XIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Resume content — formatted view or editable textarea */}
        <div ref={contentRef} className="flex-1 overflow-y-auto bg-white">
          {isEditing ? (
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full h-full min-h-[420px] px-10 py-8 text-sm font-mono text-gray-800
                         leading-relaxed resize-none outline-none border-0 focus:ring-0"
              placeholder="Paste or type resume text here…"
            />
          ) : (
            <div
              className="px-10 py-8"
              style={{ fontFamily: "'Georgia', serif" }}
            >
              {editText ? (
                <div className="max-w-[640px] mx-auto">
                  {formatResumeText(editText)}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-40 text-gray-400">
                  <FileTextIcon className="w-10 h-10 mb-3 opacity-30" />
                  <p className="text-sm">Preview not available for this resume.</p>
                  <p className="text-xs mt-1">Download the PDF or DOCX to view it.</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer — save to folder */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 shrink-0 space-y-3">
          {/* Folder row */}
          <div className="flex items-center gap-2">
            <div
              onClick={onOpenFolderPicker}
              className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-xl border-2 border-dashed cursor-pointer
                transition-colors
                ${saveFolder
                  ? 'border-brand-400 bg-brand-50 hover:bg-brand-100'
                  : 'border-gray-300 bg-white hover:border-brand-400 hover:bg-brand-50'}`}
            >
              <FolderIcon className={`w-4 h-4 shrink-0 ${saveFolder ? 'text-yellow-500' : 'text-gray-400'}`} />
              {saveFolder
                ? <span className="text-xs font-mono text-gray-800 truncate">{saveFolder}</span>
                : <span className="text-xs text-gray-400">Click to pick save folder…</span>
              }
              <span className={`ml-auto text-xs font-medium shrink-0 px-2 py-0.5 rounded
                ${saveFolder ? 'text-brand-600' : 'text-gray-500'}`}>
                {saveFolder ? 'Change' : 'Browse'}
              </span>
            </div>
          </div>

          {/* Save buttons row */}
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-gray-400">
              {isEditing
                ? 'Editing mode — changes will be saved to file'
                : 'Plain-text preview — save to folder for final formatted output'
              }
            </p>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => handleSave('pdf')}
                disabled={isSaving}
                className="btn-primary text-xs py-1.5 px-4 gap-1.5"
              >
                {isSaving ? (
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : savedType === 'pdf' ? (
                  <CheckIcon className="w-3 h-3" />
                ) : (
                  <SaveIcon className="w-3 h-3" />
                )}
                Save PDF
              </button>
              <button
                onClick={() => handleSave('docx')}
                disabled={isSaving}
                className="btn-secondary text-xs py-1.5 px-4 gap-1.5"
              >
                {isSaving ? (
                  <span className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                ) : savedType === 'docx' ? (
                  <CheckIcon className="w-3 h-3" />
                ) : (
                  <SaveIcon className="w-3 h-3" />
                )}
                Save DOCX
              </button>
              <button onClick={onClose} className="btn-secondary text-xs py-1.5 px-4">Close</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const ACCEPT = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/msword': ['.doc'],
}

export default function ResumePage() {
  const [resumeFile, setResumeFile] = useState(null)
  const [outputFolder, setOutputFolder] = useState('')
  const [folderPickerOpen, setFolderPickerOpen] = useState(false)
  const [jobDetails, setJobDetails] = useState({ job_title: '', company: '', location: '', job_url: '', description: '' })
  const [tailoredResumes, setTailoredResumes] = useState([])
  const [loading, setLoading]   = useState(false)
  const [errors, setErrors]     = useState({})

  // Preview modal state
  const [previewResume, setPreviewResume]               = useState(null)
  const [previewSaveFolder, setPreviewSaveFolder]       = useState('')
  const [previewFolderPickerOpen, setPreviewFolderPickerOpen] = useState(false)

  // Dropzone
  const onDrop = useCallback((accepted) => {
    if (accepted.length) {
      setResumeFile(accepted[0])
      setErrors((e) => ({ ...e, resume: '' }))
    }
  }, [])
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: ACCEPT, maxFiles: 1, maxSize: 10 * 1024 * 1024,
    onDropRejected: () => toast.error('Invalid file. Please upload a PDF or Word document.'),
  })

  const set = (f) => (e) => {
    setJobDetails((prev) => ({ ...prev, [f]: e.target.value }))
    setErrors((prev) => ({ ...prev, [f]: '' }))
  }

  const validate = () => {
    const e = {}
    if (!resumeFile)              e.resume       = 'Please upload your resume'
    if (!outputFolder.trim())     e.outputFolder  = 'Please specify an output folder'
    if (!jobDetails.description)  e.description   = 'Job description is required'
    return e
  }

  const handleTailor = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }

    setLoading(true)
    const formData = new FormData()
    formData.append('resume_file', resumeFile)
    formData.append('output_folder', outputFolder)
    Object.entries(jobDetails).forEach(([k, v]) => formData.append(k, v))

    try {
      const { data } = await api.post('/api/resume/tailor', formData, {
        timeout: 120000,
      })
      setTailoredResumes((prev) => [data, ...prev])
      toast.success('Resume tailored successfully!')
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDownloadTracker = async () => {
    try {
      const res = await api.get('/api/resume/tracker', { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a   = document.createElement('a')
      a.href    = url
      a.download = 'resume_tracker.xlsx'
      a.click()
      URL.revokeObjectURL(url)
      toast.success('Tracker downloaded!')
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="page-container">
      <div className="mb-8 flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI Resume Tailor</h1>
          <p className="mt-1 text-gray-500">
            Upload your resume and let Claude rewrite it for each specific role.
          </p>
        </div>
        {tailoredResumes.length > 0 && (
          <button onClick={handleDownloadTracker} className="btn-secondary">
            <FileSpreadsheetIcon className="w-4 h-4 text-green-600" /> Download Tracker
          </button>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* ── Left: Input form ── */}
        <div className="space-y-6">

          {/* Resume upload */}
          <div className="card">
            <div className="card-header">
              <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                <UploadCloudIcon className="w-4 h-4 text-brand-500" /> Upload Your Resume
              </h2>
            </div>
            <div className="card-body">
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
                  ${isDragActive ? 'border-brand-400 bg-brand-50' : 'border-gray-300 hover:border-brand-400 hover:bg-gray-50'}
                  ${errors.resume ? 'border-red-400' : ''}`}
              >
                <input {...getInputProps()} />
                {resumeFile ? (
                  <div className="flex flex-col items-center gap-2">
                    <FileTextIcon className="w-10 h-10 text-brand-500" />
                    <p className="font-medium text-gray-800">{resumeFile.name}</p>
                    <p className="text-xs text-gray-400">{(resumeFile.size / 1024).toFixed(1)} KB</p>
                    <button
                      type="button"
                      onClick={(ev) => { ev.stopPropagation(); setResumeFile(null) }}
                      className="text-xs text-red-500 hover:underline flex items-center gap-1 mt-1"
                    >
                      <TrashIcon className="w-3 h-3" /> Remove
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <UploadCloudIcon className="w-10 h-10 text-gray-300" />
                    <p className="text-sm font-medium text-gray-600">
                      {isDragActive ? 'Drop it here!' : 'Drag & drop or click to browse'}
                    </p>
                    <p className="text-xs text-gray-400">Supports PDF, DOCX, DOC — max 10 MB</p>
                  </div>
                )}
              </div>
              {errors.resume && <p className="mt-2 text-xs text-red-500">{errors.resume}</p>}
            </div>
          </div>

          {/* Output folder */}
          <div className="card">
            <div className="card-header">
              <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                <FolderOpenIcon className="w-4 h-4 text-brand-500" /> Output Folder
              </h2>
            </div>
            <div className="card-body space-y-3">
              <div
                onClick={() => setFolderPickerOpen(true)}
                className={`flex items-center gap-3 p-3 rounded-xl border-2 border-dashed cursor-pointer
                  transition-colors group
                  ${outputFolder
                    ? 'border-brand-400 bg-brand-50 hover:bg-brand-100'
                    : errors.outputFolder
                      ? 'border-red-400 bg-red-50 hover:bg-red-100'
                      : 'border-gray-300 bg-gray-50 hover:border-brand-400 hover:bg-brand-50'
                  }`}
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors
                  ${outputFolder ? 'bg-brand-100' : 'bg-gray-200 group-hover:bg-brand-100'}`}>
                  <FolderIcon className={`w-5 h-5 ${outputFolder ? 'text-yellow-500' : 'text-gray-400 group-hover:text-yellow-500'}`} />
                </div>

                <div className="flex-1 min-w-0">
                  {outputFolder ? (
                    <>
                      <p className="text-xs font-medium text-brand-700 mb-0.5">Selected folder</p>
                      <p className="text-sm font-mono text-gray-800 truncate">{outputFolder}</p>
                    </>
                  ) : (
                    <>
                      <p className="text-sm font-medium text-gray-600 group-hover:text-brand-700">
                        Click to browse and select a folder
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">Navigate your Mac's folders visually</p>
                    </>
                  )}
                </div>

                <div className={`shrink-0 flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors
                  ${outputFolder
                    ? 'bg-brand-100 text-brand-700 hover:bg-brand-200'
                    : 'bg-white text-gray-600 border border-gray-300 hover:border-brand-400 hover:text-brand-600'
                  }`}>
                  {outputFolder
                    ? <><PencilIcon className="w-3 h-3" /> Change</>
                    : <><FolderOpenIcon className="w-3 h-3" /> Browse</>
                  }
                </div>
              </div>

              <details className="group">
                <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600 list-none flex items-center gap-1 w-fit">
                  <PencilIcon className="w-3 h-3" /> Type path manually instead
                </summary>
                <div className="mt-2">
                  <input
                    type="text"
                    value={outputFolder}
                    onChange={(e) => { setOutputFolder(e.target.value); setErrors((er) => ({ ...er, outputFolder: '' })) }}
                    placeholder="/Users/yourname/Documents/tailored-resumes"
                    className="input font-mono text-sm"
                  />
                </div>
              </details>

              {errors.outputFolder
                ? <p className="text-xs text-red-500">{errors.outputFolder}</p>
                : outputFolder && (
                  <p className="text-xs text-gray-400">
                    Files will be saved as <code className="bg-gray-100 px-1 rounded">JobTitle_Location_Company.pdf/.docx</code>
                  </p>
                )
              }
            </div>
          </div>

          {/* Folder Picker Modal (for tailor output folder) */}
          <FolderPicker
            isOpen={folderPickerOpen}
            onClose={() => setFolderPickerOpen(false)}
            onSelect={(path) => {
              setOutputFolder(path)
              setErrors((er) => ({ ...er, outputFolder: '' }))
            }}
            currentPath={outputFolder}
          />

          {/* Job details */}
          <div className="card">
            <div className="card-header">
              <h2 className="font-semibold text-gray-800 flex items-center gap-2">
                <BrainCircuitIcon className="w-4 h-4 text-brand-500" /> Job Details
              </h2>
            </div>
            <div className="card-body space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Job Title <span className="text-gray-400 text-xs font-normal">(optional)</span></label>
                  <input type="text" value={jobDetails.job_title} onChange={set('job_title')}
                    placeholder="e.g. Senior Engineer"
                    className="input" />
                </div>
                <div>
                  <label className="label">Company <span className="text-gray-400 text-xs font-normal">(optional)</span></label>
                  <input type="text" value={jobDetails.company} onChange={set('company')}
                    placeholder="e.g. Acme Corp"
                    className="input" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Location</label>
                  <input type="text" value={jobDetails.location} onChange={set('location')}
                    placeholder="e.g. New York, NY" className="input" />
                </div>
                <div>
                  <label className="label">Job URL</label>
                  <input type="url" value={jobDetails.job_url} onChange={set('job_url')}
                    placeholder="https://indeed.com/..." className="input" />
                </div>
              </div>

              <div>
                <label className="label">Job Description *</label>
                <textarea
                  value={jobDetails.description}
                  onChange={set('description')}
                  rows={6}
                  placeholder="Paste the full job description here…"
                  className={`input resize-none ${errors.description ? 'border-red-400' : ''}`}
                />
                {errors.description && <p className="mt-1 text-xs text-red-500">{errors.description}</p>}
              </div>

              <button
                onClick={handleTailor}
                className="btn-primary w-full justify-center py-3"
                disabled={loading}
              >
                {loading ? (
                  <><span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Tailoring with Claude…</>
                ) : (
                  <><SparklesIcon className="w-4 h-4" /> Tailor My Resume</>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* ── Right: Tailored resumes list ── */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-800">Tailored Resumes</h2>

          {tailoredResumes.length === 0 ? (
            <div className="card p-14 text-center text-gray-400">
              <SparklesIcon className="w-12 h-12 mx-auto mb-4 opacity-20" />
              <p className="font-medium text-gray-500">No resumes tailored yet</p>
              <p className="text-sm mt-1">Fill in the form and click <strong>Tailor My Resume</strong></p>
            </div>
          ) : (
            tailoredResumes.map((r, i) => (
              <div key={i} className="card hover:shadow-md transition-shadow">
                <div className="card-body">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <CheckCircleIcon className="w-4 h-4 text-green-500 shrink-0" />
                        <h3 className="font-semibold text-gray-900 truncate">{r.filename}</h3>
                      </div>
                      {r.job_url && (
                        <a href={r.job_url} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-brand-600 hover:underline truncate block">{r.job_url}</a>
                      )}
                      {r.company_description && (
                        <p className="text-xs text-gray-500 mt-2 line-clamp-2">{r.company_description}</p>
                      )}
                    </div>
                    <div className="flex flex-col gap-2 shrink-0">
                      <button
                        onClick={() => setPreviewResume(r)}
                        className="btn-secondary text-xs py-1.5 px-3 gap-1">
                        <EyeIcon className="w-3 h-3" /> Preview & Edit
                      </button>
                      {r.pdf_path && (
                        <a href={`/api/resume/download?path=${encodeURIComponent(r.pdf_path)}`}
                          className="btn-primary text-xs py-1.5 px-3">
                          <DownloadIcon className="w-3 h-3" /> PDF
                        </a>
                      )}
                      {r.docx_path && (
                        <a href={`/api/resume/download?path=${encodeURIComponent(r.docx_path)}`}
                          className="btn-secondary text-xs py-1.5 px-3">
                          <DownloadIcon className="w-3 h-3" /> DOCX
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── Resume preview modal (rendered at root level to avoid z-index issues) ── */}
      {previewResume && (
        <ResumePreviewModal
          resume={previewResume}
          onClose={() => setPreviewResume(null)}
          saveFolder={previewSaveFolder}
          onOpenFolderPicker={() => setPreviewFolderPickerOpen(true)}
        />
      )}

      {/* Folder picker for preview save (rendered outside modal to ensure correct z-index) */}
      <FolderPicker
        isOpen={previewFolderPickerOpen}
        onClose={() => setPreviewFolderPickerOpen(false)}
        onSelect={(path) => setPreviewSaveFolder(path)}
        currentPath={previewSaveFolder}
      />
    </div>
  )
}
