import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-sm border border-muted-foreground/70 bg-card px-3 py-2 text-base leading-6 text-card-foreground shadow-xs transition-[color,box-shadow] motion-reduce:transition-none outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:border-border disabled:bg-muted disabled:text-muted-foreground aria-invalid:border-destructive md:text-sm md:leading-5",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
