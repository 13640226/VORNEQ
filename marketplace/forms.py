"""
Forms for the Saman Kherad Marketplace.

Includes:
- ProductForm: seller-facing product form
- ProductReviewForm: moderator review form
"""

from pathlib import Path

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Product, ProductReview


# ============================================================
# SETTINGS
# ============================================================

MAX_PRODUCT_FILE_SIZE = 100 * 1024 * 1024
MAX_IMAGE_SIZE = 10 * 1024 * 1024

ALLOWED_PRODUCT_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".mp3",
    ".wav",
    ".epub",
}

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


# ============================================================
# PRODUCT FORM
# ============================================================

class ProductForm(forms.ModelForm):
    """
    Form used by sellers to create and edit products.

    Sensitive fields are deliberately excluded:
    - seller
    - slug
    - status
    - is_published
    - published_at
    - created_at
    - updated_at
    """

    class Meta:

        model = Product

        fields = [
            "title",
            "short_description",
            "description",
            "category",
            "tags",
            "version",
            "price",
            "image",
            "digital_file",
        ]

        widgets = {

            "title": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "maxlength": "250",
                }
            ),

            "short_description": forms.Textarea(
                attrs={
                    "rows": 3,
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "rows": 10,
                }
            ),

            "tags": forms.TextInput(
                attrs={
                    "placeholder": _(
                        "philosophy, logic, method"
                    ),
                }
            ),

            "version": forms.TextInput(
                attrs={
                    "placeholder": "v1.0",
                }
            ),

            "price": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "0.01",
                }
            ),

            "image": forms.ClearableFileInput(
                attrs={
                    "accept": ".jpg,.jpeg,.png,.webp",
                }
            ),

            "digital_file": forms.ClearableFileInput(
                attrs={
                    "accept": ".pdf,.zip,.mp3,.wav,.epub",
                }
            ),
        }

        labels = {
            "title": _("Title"),
            "short_description": _("Short description"),
            "description": _("Full description"),
            "category": _("Category"),
            "tags": _("Tags"),
            "version": _("Version"),
            "price": _("Price"),
            "image": _("Product image"),
            "digital_file": _("Digital file"),
        }

        help_texts = {

            "tags": _(
                "Separate tags with commas."
            ),

            "image": _(
                "JPG, PNG or WebP. Maximum size: 10 MB."
            ),

            "digital_file": _(
                "PDF, ZIP, MP3, WAV or EPUB. "
                "Maximum size: 100 MB."
            ),
        }


    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    def clean_title(self):

        title = self.cleaned_data.get(
            "title",
            ""
        ).strip()

        if not title:
            raise forms.ValidationError(
                _("Title is required.")
            )

        return title


    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    def clean_description(self):

        description = self.cleaned_data.get(
            "description",
            ""
        ).strip()

        if not description:
            raise forms.ValidationError(
                _("Description is required.")
            )

        return description


    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    def clean_price(self):

        price = self.cleaned_data.get(
            "price"
        )

        if price is None:
            raise forms.ValidationError(
                _("Price is required.")
            )

        if price < 0:
            raise forms.ValidationError(
                _("Price cannot be negative.")
            )

        return price


    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    def clean_image(self):

        image = self.cleaned_data.get(
            "image"
        )

        if not image:
            return image


        # Existing stored file during edit.
        if not hasattr(image, "size"):
            return image


        if image.size > MAX_IMAGE_SIZE:

            raise forms.ValidationError(
                _("Product image cannot exceed 10 MB.")
            )


        extension = Path(
            image.name
        ).suffix.lower()


        if extension not in ALLOWED_IMAGE_EXTENSIONS:

            raise forms.ValidationError(
                _(
                    "Allowed image formats: "
                    "JPG, JPEG, PNG and WebP."
                )
            )


        return image


    # --------------------------------------------------------
    # DIGITAL FILE
    # --------------------------------------------------------

    def clean_digital_file(self):

        digital_file = self.cleaned_data.get(
            "digital_file"
        )

        if not digital_file:
            return digital_file


        # Existing stored file during edit.
        if not hasattr(
            digital_file,
            "size",
        ):
            return digital_file


        if digital_file.size > MAX_PRODUCT_FILE_SIZE:

            raise forms.ValidationError(
                _("Digital file cannot exceed 100 MB.")
            )


        extension = Path(
            digital_file.name
        ).suffix.lower()


        if extension not in ALLOWED_PRODUCT_EXTENSIONS:

            raise forms.ValidationError(
                _(
                    "Allowed product formats: "
                    "PDF, ZIP, MP3, WAV and EPUB."
                )
            )


        return digital_file


# ============================================================
# PRODUCT REVIEW FORM
# ============================================================

class ProductReviewForm(forms.ModelForm):
    """
    Moderation form.

    The moderator chooses an explicit decision and may
    provide notes and a quality score.
    """

    class Meta:

        model = ProductReview

        fields = [
            "decision",
            "notes",
            "quality_score",
        ]

        widgets = {

            "decision": forms.Select(),

            "notes": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": _(
                        "Write moderation notes..."
                    ),
                }
            ),

            "quality_score": forms.NumberInput(
                attrs={
                    "min": "1",
                    "max": "10",
                    "step": "1",
                }
            ),
        }

        labels = {
            "decision": _("Decision"),
            "notes": _("Review notes"),
            "quality_score": _("Quality score"),
        }

        help_texts = {

            "decision": _(
                "Approve, reject, or request changes."
            ),

            "quality_score": _(
                "Optional score from 1 to 10."
            ),
        }


    # --------------------------------------------------------
    # QUALITY SCORE
    # --------------------------------------------------------

    def clean_quality_score(self):

        score = self.cleaned_data.get(
            "quality_score"
        )

        if score is None:
            return score


        if not 1 <= score <= 10:

            raise forms.ValidationError(
                _("Score must be between 1 and 10.")
            )


        return score


    # --------------------------------------------------------
    # MODERATION NOTES
    # --------------------------------------------------------

    def clean(self):

        cleaned_data = super().clean()

        decision = cleaned_data.get(
            "decision"
        )

        notes = (
            cleaned_data.get(
                "notes"
            )
            or ""
        ).strip()


        # Rejection/change requests should explain why.
        if (
            decision
            in {
                ProductReview.DECISION_REJECTED,
                ProductReview.DECISION_CHANGES,
            }
            and not notes
        ):

            self.add_error(
                "notes",
                _(
                    "Please explain why the product was "
                    "rejected or what changes are required."
                ),
            )


        return cleaned_data