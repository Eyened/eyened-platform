"""
Generic table printer for Jupyter notebook display.
Provides beautiful, customizable HTML table rendering with modern styling.
"""

import enum
from typing import Any, Dict, Optional


class TablePrinter:
    """Generic table printer that creates beautiful HTML tables for Jupyter notebook display."""
    
    # Compact styling properties
    container_margin = "4px 0"
    title_margin = "0 0 4px 0"
    title_color = "#1a1a1a"
    title_font_size = "14px"
    title_font_weight = "600"
    
    table_max_width = "100%"
    table_border_radius = "0"
    table_box_shadow = "none"
    table_overflow = "visible"
    
    # Header styles (simple)
    header_background = "#f6f7f8"
    header_color = "#333333"
    header_padding = "6px 10px"
    header_font_weight = "600"
    header_font_size = "12px"
    
    # Row styles
    row_even_background = "#ffffff"
    row_odd_background = "#ffffff"
    row_hover_background = "#f3f6f9"
    row_transition = "background-color 0.12s ease"
    row_padding = "4px 8px"
    row_border_bottom = "1px solid #e5e7eb"
    
    # Field name styles
    field_font_weight = "500"
    field_color = "#495057"
    
    # Value styles
    value_color = "#212529"
    
    # Special value styles
    none_color = "#6c757d"
    none_style = "italic"
    code_background = "#f1f3f4"
    code_padding = "4px 8px"
    code_border_radius = "4px"
    code_font_family = "'Monaco', 'Menlo', 'Ubuntu Mono', monospace"
    
    # String truncation
    max_string_length = 60
    truncation_suffix = "..."
    
    def __init__(
        self,
        title: Optional[str] = None,
        theme: str = "default",
        compact: bool = False
    ):
        """
        Initialize the table printer.
        
        Args:
            title: Optional title to display above the table
            theme: Theme name ('default', 'dark', 'minimal')
            compact: Whether to use compact spacing
        """
        self.title = title
        self.theme = theme
        self.compact = compact
        
        if compact:
            self.row_padding = "2px 6px"
            self.header_padding = "4px 6px"
            self.container_margin = "2px 0"
            self.title_margin = "0 0 2px 0"
        
        if theme == "dark":
            self._apply_dark_theme()
        elif theme == "minimal":
            self._apply_minimal_theme()
    
    def _apply_dark_theme(self):
        """Apply dark theme styling."""
        self.title_color = "#ffffff"
        self.row_even_background = "#2d3748"
        self.row_odd_background = "#1a202c"
        self.row_hover_background = "#4a5568"
        self.field_color = "#e2e8f0"
        self.value_color = "#ffffff"
        self.row_border_bottom = "1px solid #4a5568"
        self.code_background = "#4a5568"
    
    def _apply_minimal_theme(self):
        """Apply minimal theme styling."""
        self.header_background = "#f8f9fa"
        self.header_color = "#495057"
        self.table_box_shadow = "none"
        self.table_border_radius = "4px"
        self.row_border_bottom = "1px solid #dee2e6"
    
    def _format_value(self, value: Any) -> str:
        """Format a value for display in the table."""
        if value is None:
            return f"<em style='color: {self.none_color}; font-style: {self.none_style};'>None</em><button type=\"button\" disabled style=\"margin-left:6px; font-size:11px; padding:0 4px; line-height:1.5; cursor:not-allowed; border:1px solid #d1d5db; background:#f9fafb; color:#9ca3af; border-radius:3px;\">Copy</button>"
        elif isinstance(value, str):
            # Escape HTML and limit length for long strings; show full on hover via title
            raw_value = value
            escaped_value = (
                raw_value
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
            )
            if len(raw_value) > self.max_string_length:
                display = (
                    escaped_value[: self.max_string_length - len(self.truncation_suffix)]
                    + self.truncation_suffix
                )
                # Build tooltip (immediate) and copy button (no <script> tag)
                tooltip_full_html = (
                    raw_value
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                )
                js_full = (
                    raw_value
                    .replace('\\', '\\\\')
                    .replace("'", "\\'")
                    .replace('\n', "\\n")
                )
                return (
                    f"<span style=\"position: relative; cursor: default;\" onmouseover=\"var t=this.querySelector('.tt'); if(t){{t.style.display='block';}}\" onmouseout=\"var t=this.querySelector('.tt'); if(t){{t.style.display='none';}}\">"
                    f"{display}"
                    f"<span style=\"display:none; position:absolute; z-index:9999; background:#111; color:#fff; padding:2px 6px; border-radius:3px; top:100%; left:0; white-space:pre-wrap; max-width:480px; font-size:11px; box-shadow:0 1px 2px rgba(0,0,0,0.2);\" class=\"tt\">{tooltip_full_html}</span>"
                    f"<button type=\"button\" onclick=\"navigator.clipboard&&navigator.clipboard.writeText('{js_full}').catch(()=>{{}}); event.stopPropagation();\" style=\"margin-left:6px; font-size:11px; padding:0 4px; line-height:1.5; cursor:pointer; border:1px solid #d1d5db; background:#f9fafb; color:#111; border-radius:3px;\">Copy</button>"
                    f"</span>"
                )
            # Not truncated, but still provide copy button
            js_full = (
                raw_value
                .replace('\\', '\\\\')
                .replace("'", "\\'")
                .replace('\n', "\\n")
            )
            return (
                f"<span style=\"position: relative; cursor: default;\">"
                f"{escaped_value}"
                f"<button type=\"button\" onclick=\"navigator.clipboard&&navigator.clipboard.writeText('{js_full}').catch(()=>{{}}); event.stopPropagation();\" style=\"margin-left:6px; font-size:11px; padding:0 4px; line-height:1.5; cursor:pointer; border:1px solid #d1d5db; background:#f9fafb; color:#111; border-radius:3px;\">Copy</button>"
                f"</span>"
            )
        elif isinstance(value, (int, float)):
            js_value = str(value).replace("'", "\\'")
            return f"{str(value)}<button type=\"button\" onclick=\"navigator.clipboard&&navigator.clipboard.writeText('{js_value}').catch(()=>{{}}); event.stopPropagation();\" style=\"margin-left:6px; font-size:11px; padding:0 4px; line-height:1.5; cursor:pointer; border:1px solid #d1d5db; background:#f9fafb; color:#111; border-radius:3px;\">Copy</button>"
        elif isinstance(value, enum.Enum):
            js_value = value.name.replace("'", "\\'")
            return f"<code style='background-color: {self.code_background}; padding: {self.code_padding}; border-radius: {self.code_border_radius}; font-family: {self.code_font_family}; font-size: 12px;'>{value.name}</code><button type=\"button\" onclick=\"navigator.clipboard&&navigator.clipboard.writeText('{js_value}').catch(()=>{{}}); event.stopPropagation();\" style=\"margin-left:6px; font-size:11px; padding:0 4px; line-height:1.5; cursor:pointer; border:1px solid #d1d5db; background:#f9fafb; color:#111; border-radius:3px;\">Copy</button>"
        else:
            # Convert any object (e.g., dicts) to string, apply same truncation/hover behavior
            raw_value = str(value)
            escaped_value = (
                raw_value
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
            )
            if len(raw_value) > self.max_string_length:
                display = (
                    escaped_value[: self.max_string_length - len(self.truncation_suffix)]
                    + self.truncation_suffix
                )
                tooltip_full_html = (
                    raw_value
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                )
                js_full = (
                    raw_value
                    .replace('\\', '\\\\')
                    .replace("'", "\\'")
                    .replace('\n', "\\n")
                )
                return (
                    f"<span style=\"position: relative; cursor: default;\" onmouseover=\"var t=this.querySelector('.tt'); if(t){{t.style.display='block';}}\" onmouseout=\"var t=this.querySelector('.tt'); if(t){{t.style.display='none';}}\">"
                    f"{display}"
                    f"<span style=\"display:none; position:absolute; z-index:9999; background:#111; color:#fff; padding:2px 6px; border-radius:3px; top:100%; left:0; white-space:pre-wrap; max-width:480px; font-size:11px; box-shadow:0 1px 2px rgba(0,0,0,0.2);\" class=\"tt\">{tooltip_full_html}</span>"
                    f"<button type=\"button\" onclick=\"navigator.clipboard&&navigator.clipboard.writeText('{js_full}').catch(()=>{{}}); event.stopPropagation();\" style=\"margin-left:6px; font-size:11px; padding:0 4px; line-height:1.5; cursor:pointer; border:1px solid #d1d5db; background:#f9fafb; color:#111; border-radius:3px;\">Copy</button>"
                    f"</span>"
                )
            js_full = (
                raw_value
                .replace('\\', '\\\\')
                .replace("'", "\\'")
                .replace('\n', "\\n")
            )
            return (
                f"<span style=\"position: relative; cursor: default;\">"
                f"{escaped_value}"
                f"<button type=\"button\" onclick=\"navigator.clipboard&&navigator.clipboard.writeText('{js_full}').catch(()=>{{}}); event.stopPropagation();\" style=\"margin-left:6px; font-size:11px; padding:0 4px; line-height:1.5; cursor:pointer; border:1px solid #d1d5db; background:#f9fafb; color:#111; border-radius:3px;\">Copy</button>"
                f"</span>"
            )
    
    def _repr_html_(self, data: Dict[str, Any]) -> str:
        """
        Generate beautiful HTML representation of the data as a table.
        
        Args:
            data: Dictionary of key-value pairs to display
            
        Returns:
            HTML string for Jupyter display
        """
        if not data:
            title_html = f"""
                <h4 style="margin: {self.title_margin}; color: {self.title_color}; font-size: {self.title_font_size}; font-weight: {self.title_font_weight};">
                    {self.title}
                </h4>
            """ if self.title else ""
            return f"""
            <div style="margin: {self.container_margin};">
                {title_html}
                <p style="color: {self.none_color}; font-style: {self.none_style};"><em>No data to display</em></p>
            </div>
            """
        
        # Create title HTML
        title_html = f"""
            <h4 style="margin: {self.title_margin}; color: {self.title_color}; font-size: {self.title_font_size}; font-weight: {self.title_font_weight};">
                {self.title}
            </h4>
        """ if self.title else ""
        
        # Build the table HTML
        html = f"""
        <div style="margin: {self.container_margin};">
            {title_html}
            <div style="display: inline-block; border-radius: {self.table_border_radius}; box-shadow: {self.table_box_shadow}; overflow: {self.table_overflow};">
                <table style="width: auto; table-layout: auto; border-collapse: collapse; margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <thead>
                        <tr>
                            <th style="background: {self.header_background}; color: {self.header_color}; padding: {self.header_padding}; text-align: left; font-weight: {self.header_font_weight}; font-size: {self.header_font_size}; border-bottom: {self.row_border_bottom};">Field</th>
                            <th style="background: {self.header_background}; color: {self.header_color}; padding: {self.header_padding}; text-align: left; font-weight: {self.header_font_weight}; font-size: {self.header_font_size}; border-bottom: {self.row_border_bottom};">Value</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for i, (key, value) in enumerate(data.items()):
            display_value = self._format_value(value)
            
            # Alternate row colors
            row_background = self.row_even_background if i % 2 == 0 else self.row_odd_background
            
            html += f"""
                        <tr style="background-color: {row_background}; transition: {self.row_transition};" 
                            onmouseover="this.style.backgroundColor='{self.row_hover_background}';" 
                            onmouseout="this.style.backgroundColor='{row_background}';">
                            <td style="border-bottom: {self.row_border_bottom}; padding: {self.row_padding}; font-weight: {self.field_font_weight}; color: {self.field_color}; vertical-align: top;">{key}</td>
                            <td style="border-bottom: {self.row_border_bottom}; padding: {self.row_padding}; color: {self.value_color}; vertical-align: top;">{display_value}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        </div>
        """
        
        return html
    
    def print_table(self, data: Dict[str, Any]) -> str:
        """
        Generate beautiful HTML table for the given data.
        
        Args:
            data: Dictionary of key-value pairs to display
            
        Returns:
            HTML string for Jupyter display
        """
        return self._repr_html_(data)
    