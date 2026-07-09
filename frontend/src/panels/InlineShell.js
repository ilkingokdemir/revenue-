// Inline panel shells shared by review/system tool panels (iter 390)
export const InlineContent = ({ children, className = "", ...rest }) => (
  <div className={`bg-white border border-stone-200/80 rounded-xl shadow-card p-6 w-full ${className}`} {...rest}>{children}</div>
);
export const InlineHeader = ({ children, className = "" }) => <div className={`mb-4 ${className}`}>{children}</div>;
export const InlineTitle = ({ children, className = "" }) => <h2 className={`text-lg font-semibold ${className}`}>{children}</h2>;
