import Image from "next/image"
import { APP_TITLE, LOGO_SRC } from "@/lib/constants"
import { ThemeToggle } from "@/components/theme-toggle"

/**
 * AppHeader — top navigation bar.
 * To customize: edit APP_TITLE and LOGO_SRC in lib/constants.ts.
 */
export function AppHeader() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 text-foreground backdrop-blur">
      <div className="w-full px-5 h-16 flex items-center gap-3">
        {LOGO_SRC && (
          <Image
            src={LOGO_SRC}
            alt={`${APP_TITLE} logo`}
            width={28}
            height={28}
            className="shrink-0"
          />
        )}
        <div className="header-title"><span>{APP_TITLE}</span><small>Snowflake App Runtime</small></div>
        <span className="live-status"><i/>LIVE DATA</span>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
