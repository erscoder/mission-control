import { Header } from '@/components/Header'
import { Hero } from '@/components/Hero'
import { HowItWorks } from '@/components/HowItWorks'
import { Pipeline } from '@/components/Pipeline'
import { CaseStudy } from '@/components/CaseStudy'
import { Portfolio } from '@/components/Portfolio'
import { About } from '@/components/About'
import { Footer } from '@/components/Footer'
import { VoicesBackground } from '@/components/VoicesBackground'

export default function Home() {
  return (
    <main className="relative min-h-screen">
      <VoicesBackground />
      <div className="relative">
        <Header />
        <Hero />
        <HowItWorks />
        <Pipeline />
        <CaseStudy />
        <Portfolio />
        <About />
        <Footer />
      </div>
    </main>
  )
}
