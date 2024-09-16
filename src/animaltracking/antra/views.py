from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.urls import reverse_lazy
from pathlib import Path

# Create your views here.


def index(request):
    return render(request, "antra/index.html")


class MyLoginView(LoginView):
    # template_name = "antra/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        """Return url of next page."""
        return reverse_lazy("antra:index")

    def form_invalid(self, form):
        """Return error message if wrong username or password is given."""
        messages.error(self.request, "Invalid username or password")
        return self.render_to_response(self.get_context_data(form=form))


from django.views.generic import ListView
from .models import MediaFile

class MediaFileListView(ListView):
    model = MediaFile
    template_name = 'antra/mediafile_list.html'
    context_object_name = 'mediafiles'
    paginate_by = 10  # Display 10 media files per page

    # Optionally, you can add custom ordering, pagination, etc.
    # For example, order by `uploaded_at`:
    queryset = MediaFile.objects.all().order_by('-uploaded_at')

    # You can override `get_context_data()` if you need to add extra context to the template
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context['extra_data'] = 'Additional information if needed'
    #     return context

def import_videos(request):

    import_dir = Path("/antra_import")
    messages.info(request, f"Importing videos from {import_dir}, {list(import_dir.glob('*.*'))}")

    return redirect("antra:mediafile-list")