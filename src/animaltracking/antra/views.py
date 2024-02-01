from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.urls import reverse_lazy

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
