// Carbon modal/_modal.scss at md / lg / xlg: xs 48% / 32% / 24%, sm 60% / 42% / 36%,
// lg 96% / 84% / 72% (max height 90% at md from ui/dialog, 96% from lg).
export const modalSizeClasses = {
    xs: "md:w-12/25 lg:max-h-12/25 lg:w-8/25 xlg:w-6/25",
    sm: "md:w-3/5 lg:max-h-18/25 lg:w-21/50 xlg:w-9/25",
    lg: "md:w-24/25 lg:max-h-24/25 lg:w-21/25 xlg:w-18/25",
} as const;
