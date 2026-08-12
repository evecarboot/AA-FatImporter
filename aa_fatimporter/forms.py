from django import forms


class FatUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Alliance FAT CSV export",
        help_text="Upload the FAT export file provided by the alliance.",
    )
