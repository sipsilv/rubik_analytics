import * as React from "react"
import { Check } from "lucide-react"

interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
    onCheckedChange?: (checked: boolean) => void
}

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
    ({ className, onCheckedChange, onChange, ...props }, ref) => {
        return (
            <div className="relative inline-flex items-center justify-center w-5 h-5">
                <input
                    type="checkbox"
                    className="peer appearance-none w-5 h-5 border border-border rounded bg-secondary/10 checked:bg-primary checked:border-primary transition-colors focus:ring-2 focus:ring-primary/20 cursor-pointer"
                    onChange={(e) => {
                        onChange?.(e)
                        onCheckedChange?.(e.target.checked)
                    }}
                    ref={ref}
                    {...props}
                />
                <Check className="absolute w-3.5 h-3.5 text-white pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity" />
            </div>
        )
    }
)
Checkbox.displayName = "Checkbox"

export { Checkbox }
