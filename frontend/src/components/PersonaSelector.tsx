import React, { useState } from 'react'
import { User, Briefcase, Scale, DollarSign, Shield, Heart, Globe, Home, Building, Book, Leaf, FileText, TrendingUp, Gavel, Building2, Ship, Activity } from 'lucide-react'

interface Persona {
  id: string
  name: string
  title: string
  icon: React.ReactNode
  description: string
  expertiseAreas: string[]
  color: string
  gradient: string
}

const PERSONAS: Persona[] = [
  {
    id: 'litigation_specialist',
    name: 'Advocate Sharma',
    title: 'Litigation Specialist',
    icon: <Scale className="w-6 h-6" />,
    description: 'Expert trial lawyer with 20+ years in civil and commercial litigation',
    expertiseAreas: ['Trial Strategy', 'Evidence Analysis', 'Motion Practice', 'Appeals'],
    color: 'blue',
    gradient: 'from-blue-500 to-blue-700'
  },
  {
    id: 'corporate_counsel',
    name: 'Ms. Priya Kapoor',
    title: 'Corporate Counsel',
    icon: <Briefcase className="w-6 h-6" />,
    description: 'Senior corporate lawyer specializing in M&A and corporate governance',
    expertiseAreas: ['M&A', 'Corporate Governance', 'Commercial Contracts', 'Securities Law'],
    color: 'indigo',
    gradient: 'from-indigo-500 to-indigo-700'
  },
  {
    id: 'intellectual_property',
    name: 'Dr. Rajesh Patel',
    title: 'IP Specialist',
    icon: <FileText className="w-6 h-6" />,
    description: 'IP attorney with PhD specializing in patents and tech licensing',
    expertiseAreas: ['Patents', 'Trademarks', 'Copyright', 'Technology Transfer'],
    color: 'purple',
    gradient: 'from-purple-500 to-purple-700'
  },
  {
    id: 'tax_attorney',
    name: 'CA Suresh Kumar',
    title: 'Tax Attorney',
    icon: <DollarSign className="w-6 h-6" />,
    description: 'Tax lawyer and CA specializing in corporate tax and international taxation',
    expertiseAreas: ['Corporate Tax', 'GST', 'International Tax', 'Tax Disputes'],
    color: 'green',
    gradient: 'from-green-500 to-green-700'
  },
  {
    id: 'criminal_defense',
    name: 'Senior Advocate Mehra',
    title: 'Criminal Defense',
    icon: <Shield className="w-6 h-6" />,
    description: 'Renowned criminal defense attorney with expertise in constitutional law',
    expertiseAreas: ['Criminal Defense', 'Bail Applications', 'Constitutional Rights', 'Appeals'],
    color: 'red',
    gradient: 'from-red-500 to-red-700'
  },
  {
    id: 'family_law',
    name: 'Advocate Anjali Desai',
    title: 'Family Law Expert',
    icon: <Heart className="w-6 h-6" />,
    description: 'Compassionate family law attorney specializing in divorce and custody',
    expertiseAreas: ['Divorce', 'Child Custody', 'Matrimonial Property', 'Domestic Violence'],
    color: 'pink',
    gradient: 'from-pink-500 to-pink-700'
  },
  {
    id: 'immigration_lawyer',
    name: 'Advocate Rahman Ali',
    title: 'Immigration Specialist',
    icon: <Globe className="w-6 h-6" />,
    description: 'Immigration attorney specializing in visas and citizenship',
    expertiseAreas: ['Work Visas', 'Citizenship', 'Asylum Law', 'Immigration Appeals'],
    color: 'teal',
    gradient: 'from-teal-500 to-teal-700'
  },
  {
    id: 'real_estate',
    name: 'Ms. Kavita Reddy',
    title: 'Real Estate Attorney',
    icon: <Home className="w-6 h-6" />,
    description: 'Real estate lawyer specializing in property transactions and RERA',
    expertiseAreas: ['Property Transactions', 'Title Examination', 'RERA Compliance', 'Leases'],
    color: 'orange',
    gradient: 'from-orange-500 to-orange-700'
  },
  {
    id: 'employment_law',
    name: 'Advocate Verma',
    title: 'Employment Law Expert',
    icon: <Building className="w-6 h-6" />,
    description: 'Employment attorney specializing in labor law and workplace disputes',
    expertiseAreas: ['Wrongful Termination', 'Employment Contracts', 'Discrimination', 'Wage Disputes'],
    color: 'yellow',
    gradient: 'from-yellow-500 to-yellow-700'
  },
  {
    id: 'constitutional_law',
    name: 'Prof. Malhotra',
    title: 'Constitutional Law Scholar',
    icon: <Book className="w-6 h-6" />,
    description: 'Constitutional law expert and Supreme Court advocate',
    expertiseAreas: ['Fundamental Rights', 'PIL', 'Writ Petitions', 'Judicial Review'],
    color: 'amber',
    gradient: 'from-amber-500 to-amber-700'
  },
  {
    id: 'environmental_law',
    name: 'Dr. Ananya Bose',
    title: 'Environmental Law Specialist',
    icon: <Leaf className="w-6 h-6" />,
    description: 'Environmental lawyer specializing in climate law and compliance',
    expertiseAreas: ['Environmental Clearances', 'Pollution Control', 'Climate Law', 'ESG Compliance'],
    color: 'emerald',
    gradient: 'from-emerald-500 to-emerald-700'
  },
  {
    id: 'bankruptcy_specialist',
    name: 'Advocate Sengupta',
    title: 'Insolvency & Bankruptcy Expert',
    icon: <TrendingUp className="w-6 h-6" />,
    description: 'Insolvency professional specializing in IBC and debt restructuring',
    expertiseAreas: ['CIRP', 'Liquidation', 'Debt Restructuring', 'Creditor Rights'],
    color: 'slate',
    gradient: 'from-slate-500 to-slate-700'
  },
  {
    id: 'compliance_officer',
    name: 'Ms. Lakshmi Iyer',
    title: 'Compliance Officer',
    icon: <FileText className="w-6 h-6" />,
    description: 'Compliance expert specializing in regulatory frameworks',
    expertiseAreas: ['Regulatory Compliance', 'AML/KYC', 'Data Privacy', 'Internal Audits'],
    color: 'cyan',
    gradient: 'from-cyan-500 to-cyan-700'
  },
  {
    id: 'arbitration_mediator',
    name: 'Justice (Retd.) Khanna',
    title: 'Arbitration & Mediation Expert',
    icon: <Gavel className="w-6 h-6" />,
    description: 'Retired judge specializing in alternative dispute resolution',
    expertiseAreas: ['Commercial Arbitration', 'Mediation', 'Award Enforcement', 'ADR'],
    color: 'gray',
    gradient: 'from-gray-500 to-gray-700'
  },
  {
    id: 'startup_legal_advisor',
    name: 'Advocate Nisha Singh',
    title: 'Startup Legal Advisor',
    icon: <TrendingUp className="w-6 h-6" />,
    description: 'Tech-savvy lawyer specializing in startup formation and VC',
    expertiseAreas: ['Company Formation', 'Fundraising', 'ESOP', 'Tech Contracts'],
    color: 'violet',
    gradient: 'from-violet-500 to-violet-700'
  },
  {
    id: 'regulatory_affairs',
    name: 'Mr. Venkatesan',
    title: 'Regulatory Affairs Specialist',
    icon: <Building2 className="w-6 h-6" />,
    description: 'Regulatory expert specializing in sector-specific regulations',
    expertiseAreas: ['Pharma Regulations', 'Telecom', 'Financial Services', 'FSSAI'],
    color: 'sky',
    gradient: 'from-sky-500 to-sky-700'
  },
  {
    id: 'international_trade',
    name: 'Ms. Fernandes',
    title: 'International Trade Lawyer',
    icon: <Ship className="w-6 h-6" />,
    description: 'International trade attorney specializing in cross-border transactions',
    expertiseAreas: ['Trade Agreements', 'Import/Export', 'Trade Remedies', 'FDI'],
    color: 'blue',
    gradient: 'from-blue-600 to-blue-800'
  },
  {
    id: 'healthcare_law',
    name: 'Dr. Mehta',
    title: 'Healthcare & Medical Law Expert',
    icon: <Activity className="w-6 h-6" />,
    description: 'Healthcare attorney with medical training',
    expertiseAreas: ['Medical Malpractice', 'Healthcare Compliance', 'Patient Rights', 'Clinical Trials'],
    color: 'rose',
    gradient: 'from-rose-500 to-rose-700'
  },
]

interface PersonaSelectorProps {
  selectedPersona: string | null
  onSelectPersona: (personaId: string) => void
  onClose: () => void
}

const PersonaSelector: React.FC<PersonaSelectorProps> = ({
  selectedPersona,
  onSelectPersona,
  onClose
}) => {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  const filteredPersonas = PERSONAS.filter(persona => {
    const matchesSearch = persona.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         persona.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         persona.expertiseAreas.some(area => area.toLowerCase().includes(searchTerm.toLowerCase()))

    return matchesSearch
  })

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-7xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-8 py-6 text-white">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-3xl font-bold">Choose Your Legal Expert</h2>
            <button
              onClick={onClose}
              className="text-white hover:bg-white hover:bg-opacity-20 rounded-full p-2 transition-all"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p className="text-blue-100">Select from 18 specialized legal AI personas, each trained for specific practice areas</p>

          {/* Search */}
          <div className="mt-4">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by name, specialty, or expertise area..."
              className="w-full px-4 py-3 rounded-lg bg-white bg-opacity-20 backdrop-blur-md text-white placeholder-blue-200 border border-white border-opacity-30 focus:outline-none focus:ring-2 focus:ring-white focus:ring-opacity-50"
            />
          </div>
        </div>

        {/* Personas Grid */}
        <div className="p-8 overflow-y-auto max-h-[calc(90vh-200px)]">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPersonas.map((persona) => {
              const isSelected = selectedPersona === persona.id

              return (
                <div
                  key={persona.id}
                  onClick={() => onSelectPersona(persona.id)}
                  className={`
                    relative group cursor-pointer rounded-xl overflow-hidden
                    transition-all duration-300 transform hover:scale-105
                    ${isSelected ? 'ring-4 ring-blue-500 shadow-2xl' : 'hover:shadow-xl'}
                  `}
                >
                  {/* Gradient Background */}
                  <div className={`
                    absolute inset-0 bg-gradient-to-br ${persona.gradient}
                    opacity-90 group-hover:opacity-100 transition-opacity
                  `} />

                  {/* Content */}
                  <div className="relative p-6 text-white">
                    {/* Icon & Selected Indicator */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="bg-white bg-opacity-20 backdrop-blur-md rounded-lg p-3">
                        {persona.icon}
                      </div>
                      {isSelected && (
                        <div className="bg-white text-blue-600 rounded-full p-1">
                          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        </div>
                      )}
                    </div>

                    {/* Name & Title */}
                    <h3 className="text-xl font-bold mb-1">{persona.name}</h3>
                    <p className="text-white text-opacity-90 text-sm font-medium mb-3">
                      {persona.title}
                    </p>

                    {/* Description */}
                    <p className="text-white text-opacity-80 text-sm mb-4 line-clamp-2">
                      {persona.description}
                    </p>

                    {/* Expertise Tags */}
                    <div className="flex flex-wrap gap-2">
                      {persona.expertiseAreas.slice(0, 3).map((area, idx) => (
                        <span
                          key={idx}
                          className="text-xs px-2 py-1 bg-white bg-opacity-20 backdrop-blur-md rounded-full"
                        >
                          {area}
                        </span>
                      ))}
                      {persona.expertiseAreas.length > 3 && (
                        <span className="text-xs px-2 py-1 bg-white bg-opacity-20 backdrop-blur-md rounded-full">
                          +{persona.expertiseAreas.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Hover Overlay */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-transparent opacity-0 group-hover:opacity-40 transition-opacity" />
                </div>
              )
            })}
          </div>

          {filteredPersonas.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500 text-lg">No personas found matching your search</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-8 py-4 border-t border-gray-200 flex items-center justify-between">
          <p className="text-sm text-gray-600">
            {filteredPersonas.length} {filteredPersonas.length === 1 ? 'persona' : 'personas'} available
          </p>
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

export default PersonaSelector
