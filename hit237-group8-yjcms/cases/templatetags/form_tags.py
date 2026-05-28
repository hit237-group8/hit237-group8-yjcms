from django import template

register = template.Library()


@register.filter
def bootstrap_field(bound_field):
    widget = bound_field.field.widget
    classes = widget.attrs.get("class", "")

    if widget.input_type == "select":
        base = "form-select"
    elif widget.input_type in {"checkbox", "radio"}:
        base = "form-check-input"
    elif widget.input_type == "textarea":
        base = "form-control"
    else:
        base = "form-control"

    if bound_field.errors and "is-invalid" not in classes:
        classes = f"{classes} is-invalid".strip()

    classes = f"{classes} {base}".strip() if base not in classes else classes.strip()
    return bound_field.as_widget(attrs={"class": classes})
