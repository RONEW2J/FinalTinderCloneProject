from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend # Import DjangoFilterBackend
from django.db.models import Q, Case, When, F, IntegerField
from django.contrib import messages

from .models import Profile, Interest, Photo # Added Photo
from apps.actions.models import Swipe # For filtering based on swipes
from apps.matches.models import Match # For filtering based on matches
from .serializers import ProfileSerializer, InterestSerializer, PhotoSerializer # Added PhotoSerializer
from .forms import ProfileEditForm, PhotoUploadForm

# GeoDjango imports are no longer needed for profile editing if using city
# from django.contrib.gis.geos import Point
# from django.contrib.gis.measure import D # Distance object
# from django.contrib.gis.db.models.functions import Distance as DistanceFunc
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseNotFound
from django.views.decorators.http import require_POST

# Create your views here.

class UserProfileDetailView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update the profile of the currently authenticated user.
    """
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Ensure a profile exists for the user, or create one if using signals isn't enough
        # (though signals should handle this)
        profile, created = Profile.objects.get_or_create(user=self.request.user)
        return profile

class InterestListCreateView(generics.ListCreateAPIView):
    """
    List all interests or create a new one.
    """
    queryset = Interest.objects.all()
    serializer_class = InterestSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Allow anyone to see, only auth to create

class ProfileListView(generics.ListAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Assuming 'interests' can be filtered by ID or name (e.g., interests__name=Music)
    # 'gender' and 'bio' were removed as they are not on the current Profile model.
    # Add them to the model if you intend to filter/search by them.
    filterset_fields = ['interests', 'age'] # Example: ?age=25 or ?interests=1 (by ID)
    search_fields = ['user__username', 'interests__name'] # Search by username or interest names
    ordering_fields = ['age', 'user__date_joined', 'distance'] # Allow ordering by these, 'distance' if annotated
    
    def get_queryset(self):
        user = self.request.user
        queryset = Profile.objects.select_related('user').prefetch_related('interests', 'photos').exclude(user=user)

        # 1. Filter out users the current user has already swiped "PASS" on.
        passed_user_ids = Swipe.objects.filter(
            swiper=user,
            action='PASS'
        ).values_list('swiped_user_id', flat=True)
        queryset = queryset.exclude(user_id__in=passed_user_ids)

        # 2. Filter out users the current user has already matched with.
        matches_as_user1 = Match.objects.filter(user1=user).values_list('user2_id', flat=True)
        matches_as_user2 = Match.objects.filter(user2=user).values_list('user1_id', flat=True)
        all_matched_user_ids = set(list(matches_as_user1) + list(matches_as_user2))
        queryset = queryset.exclude(user_id__in=all_matched_user_ids)

        # 3. Filter by city and interests (if provided in query params)
        # This replaces the GeoDjango proximity filter
        city_id = self.request.query_params.get('city')
        if city_id:
            queryset = queryset.filter(city_id=city_id)

        interest_ids = self.request.query_params.getlist('interests') # getlist for multiple values
        if interest_ids:
            # Filter profiles that have at least one of the specified interests.
            # If you need profiles that have ALL specified interests, you'd loop and chain filters.
            queryset = queryset.filter(interests__id__in=interest_ids).distinct()

        # The old GeoDjango proximity filter is removed.
        # If you still need radius-based filtering with cities, you'd need a more complex setup:
        # 1. Store lat/lon on your City model.
        # 2. Get the user's city's lat/lon.
        # 3. Find cities within the radius of the user's city's lat/lon.
        # 4. Filter profiles by those cities.
        # This is significantly different from the previous PointField-based distance.
        # For now, we assume filtering is by selected city and interests directly.

        # Example of old GeoDjango proximity filter (REMOVED):
        # try:
        #     user_profile = user.profile
        #     if user_profile.location: # This was the PointField
        #         user_location = user_profile.location 
                
        #         search_radius_km_str = self.request.query_params.get('radius_km', '50')
        #         # ... (rest of radius logic) ...
        #         queryset = queryset.annotate(distance=DistanceFunc('location', user_location)) # ...
        # except Profile.DoesNotExist:
        #     pass 
        # except AttributeError: 
        #     pass

        return queryset

# You'll need to create these views for photo management
class PhotoListCreateView(generics.ListCreateAPIView):
    serializer_class = PhotoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Photo.objects.filter(profile__user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)

class PhotoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PhotoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Photo.objects.filter(profile__user=self.request.user)
    
@login_required
def user_profile_display_view(request):
    # Assuming a Profile is created for each User, e.g., via a signal
    # If not, you might need get_or_create
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        # Handle case where profile doesn't exist, maybe create it
        # or redirect to a profile creation page.
        # For now, let's assume it should exist.
        # If you have a signal to create Profile on User creation, this should be fine.
        # If not, you might want to redirect to a "create profile" page.
        return render(request, 'profiles/profile_not_found.html') # Or some other handling

    context = {'profile': profile}
    return render(request, 'profiles/profile_display.html', context)

@login_required
def profile_edit_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, "Profile not found. Please contact support.")
        return redirect('profiles:profile-display')

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        print(f"Form submitted. POST data: {request.POST}")
        if form.is_valid():
            print(f"Form is valid. Cleaned data: {form.cleaned_data}")
            
            # The form now handles the 'city' field directly.
            # No need for manual latitude/longitude or Point object creation here.
            updated_profile = form.save() # commit=True is default, this will save the instance and M2M data if form is configured correctly.
                                          # If you had commit=False, you'd need form.save_m2m() later.

            # If ProfileEditForm is a ModelForm and 'interests' is a ManyToManyField,
            # and it's included in form.Meta.fields, form.save() handles it.
            # If you used commit=False above, you would need:
            # updated_profile.save() # first save the instance
            # form.save_m2m()      # then save M2M data
            
            # Critical Debugging Step: Re-fetch from DB and check bio
            fresh_profile_check = Profile.objects.get(pk=updated_profile.pk)
            print(f"Bio from DB immediately after save: {fresh_profile_check.bio}")
            
            # Debug print to verify save
            print(f"Updated profile bio: {updated_profile.bio}, city: {updated_profile.city}")
            
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profiles:profile-display')
        else:
            print(f"Form is invalid. Errors: {form.errors}") # For debugging if form validation fails
    else:
        form = ProfileEditForm(instance=profile)
    return render(request, 'profiles/profile_edit_form.html', {'form': form, 'profile': profile})

@login_required
def photo_upload_view(request):
    profile = request.user.profile # Assuming profile exists
    if request.method == 'POST':
        form = PhotoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.profile = profile

            # If this photo is marked as the avatar, unmark any other avatars for this profile
            if photo.is_profile_avatar: # This is True if the checkbox was checked
                Photo.objects.filter(profile=profile, is_profile_avatar=True).update(is_profile_avatar=False)
            photo.save()
            messages.success(request, 'Photo uploaded successfully!')
            return redirect('profiles:profile-display') # Redirect to view profile
    else:
        form = PhotoUploadForm()
    return render(request, 'profiles/photo_upload_form.html', {'form': form})

@login_required
@require_POST # Ensure this view only accepts POST requests for deletion
def photo_delete_view(request, photo_id):
    try:
        photo = get_object_or_404(Photo, pk=photo_id)
    except Photo.DoesNotExist:
         # This case is actually handled by get_object_or_404, but good for clarity
        if request.headers.get('x-requested-with') == 'XMLHttpRequest': # AJAX
            return JsonResponse({'status': 'error', 'message': 'Photo not found.'}, status=404)
        messages.error(request, 'Photo not found.')
        return redirect('profiles:profile-display') # Or wherever appropriate

    # Security check: Ensure the logged-in user owns the profile to which this photo belongs
    if photo.profile.user != request.user:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest': # AJAX
            return JsonResponse({'status': 'error', 'message': 'You do not have permission to delete this photo.'}, status=403)
        messages.error(request, 'You do not have permission to delete this photo.')
        return redirect('profiles:profile-display') # Or wherever appropriate

    # If this was the avatar, and you want to clear the avatar status, you could do it here.
    # However, the `main_image` property will now handle finding a new avatar or returning None.
    # If you wanted to explicitly pick a new avatar, that's more complex UI.
    
    photo_was_avatar = photo.is_profile_avatar
    photo.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest': # AJAX
        response_data = {'status': 'success', 'message': 'Photo deleted successfully.'}
        if photo_was_avatar:
            # Optionally, tell the client the avatar might have changed so it can refresh the main image
            response_data['avatar_changed'] = True 
            # You might also want to send back the URL of the new main_image if one is auto-selected by the property
            new_main_image = request.user.profile.main_image
            response_data['new_avatar_url'] = new_main_image.url if new_main_image else None
        return JsonResponse(response_data)
    
    messages.success(request, 'Photo deleted successfully!')
    return redirect('profiles:profile-display')