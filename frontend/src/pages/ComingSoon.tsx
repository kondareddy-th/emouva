import { Construction } from 'lucide-react'

export default function ComingSoon({ title }: { title: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="w-14 h-14 rounded-xl bg-surface-3 flex items-center justify-center mx-auto mb-4">
          <Construction className="w-7 h-7 text-text-tertiary" />
        </div>
        <h1 className="text-title text-text-primary mb-2">
          {title}
        </h1>
        <p className="text-[14px] text-text-tertiary max-w-xs mx-auto">
          This section is under development.
        </p>
      </div>
    </div>
  )
}
