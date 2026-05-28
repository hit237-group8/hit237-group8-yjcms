from django import template
from django.forms import Select, SelectMultiple, Textarea

register = template.Library()


@register.filter(name='add_class')
def add_class(field, css_class):
    """Add a CSS class to a form field widget."""
    return field.as_widget(attrs={'class': css_class})


@register.filter(name='bootstrap_field')
def bootstrap_field(field):
    """Apply the correct Bootstrap class based on widget type."""
    widget = field.field.widget
    if isinstance(widget, (Select, SelectMultiple)):
        css = 'form-select'
    else:
        css = 'form-control'
    if field.errors:
        css += ' is-invalid'
    return field.as_widget(attrs={'class': css})
