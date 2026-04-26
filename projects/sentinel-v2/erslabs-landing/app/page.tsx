import { Hero } from '@/components/Hero'
import { HowItWorks } from '@/components/HowItWorks'
import { Pipeline } from '@/components/Pipeline'
import { CaseStudy } from '@/components/CaseStudy'
import { Portfolio } from '@/components/Portfolio'
import { About } from '@/components/About'
import { Footer } from '@/components/Footer'

export default function Home() {
  return (
    <main className="min-h-screen">
      <Hero />
      <HowItWorks />
      <Pipeline />
      <CaseStudy />
      <Portfolio />
      <About />
      <Footer />
    </main>
  )
}
