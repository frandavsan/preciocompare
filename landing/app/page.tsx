import { BackgroundBlobs } from "@/components/site/background-blobs"
import { Navbar } from "@/components/site/navbar"
import { LandingIntro } from "@/components/site/landing-intro"
import { Hero } from "@/components/site/hero"
import { Features } from "@/components/site/features"
import { Workflow } from "@/components/site/workflow"
import { Argentina } from "@/components/site/argentina"
import { DashboardPreview } from "@/components/site/dashboard-preview"
import { CTA } from "@/components/site/cta"
import { Footer } from "@/components/site/footer"

export default function HomePage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-background">
      <BackgroundBlobs />
      <div className="relative z-10">
        <Navbar />
        <LandingIntro />
        <Hero />
        <Features />
        <Workflow />
        <Argentina />
        <DashboardPreview />
        <CTA />
        <Footer />
      </div>
    </main>
  )
}
