from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import FormView

from aa_fatimporter.forms import FatUploadForm
from aa_fatimporter.services import parse_fat_csv


class FatImportView(FormView):
    template_name = "aa_fatimporter/upload.html"
    form_class = FatUploadForm
    success_url = "/"

    def form_valid(self, form):
        uploaded_file = form.cleaned_data["csv_file"]
        data = uploaded_file.read().decode("utf-8", errors="replace")
        records = parse_fat_csv(data)

        if not records:
            messages.error(self.request, "No valid FAT rows were found in the uploaded CSV.")
            return redirect(self.success_url)

        messages.success(self.request, f"Imported {len(records)} FAT entries.")
        return super().form_valid(form)
