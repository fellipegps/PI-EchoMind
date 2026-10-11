import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm leading-5 font-medium transition-[color,background-color,box-shadow] motion-reduce:transition-none active:shadow-inner disabled:pointer-events-none disabled:border-border disabled:bg-muted disabled:text-muted-foreground aria-disabled:pointer-events-none aria-disabled:bg-muted aria-disabled:text-muted-foreground [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background aria-invalid:border-destructive",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary-hover",
        destructive:
          "bg-destructive text-destructive-foreground hover:shadow-sm",
        outline:
          "border border-input bg-background text-foreground shadow-xs hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-accent hover:shadow-sm",
        ghost:
          "text-foreground hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-11 px-4 py-2 has-[>svg]:px-3",
        xs: "h-9 gap-1 px-2 text-xs max-md:min-h-11 max-md:min-w-11 [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11 has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-9 gap-1.5 px-3 max-md:min-h-11 max-md:min-w-11 [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11 has-[>svg]:px-2.5",
        lg: "h-12 px-6 has-[>svg]:px-4",
        icon: "size-11",
        "icon-xs": "size-9 max-md:min-h-11 max-md:min-w-11 [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-9 max-md:min-h-11 max-md:min-w-11 [@media(pointer:coarse)]:min-h-11 [@media(pointer:coarse)]:min-w-11",
        "icon-lg": "size-12",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
