"""
Views for the Saman Kherad Marketplace.

سامان خرد — بازار دیجیتال

Includes:
- Public marketplace
- Product detail
- Seller dashboard
- Product creation
- Product editing
- Staff review queue
- Product moderation
"""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import ProductForm, ProductReviewForm
from .models import Product, ProductReview


# ============================================================
# PUBLIC MARKETPLACE
# ============================================================

def index(request):
    """
    Display publicly available marketplace products.

    A product is public only when:
    - status == approved
    - is_published == True
    """

    query = request.GET.get(
        "q",
        "",
    ).strip()

    category = request.GET.get(
        "category",
        "",
    ).strip()


    # --------------------------------------------------------
    # Public products
    # --------------------------------------------------------

    products = Product.objects.filter(
        status=Product.STATUS_APPROVED,
        is_published=True,
    ).select_related(
        "seller",
    )


    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    if query:

        products = products.filter(

            Q(
                title__icontains=query,
            )

            | Q(
                short_description__icontains=query,
            )

            | Q(
                description__icontains=query,
            )

            | Q(
                tags__icontains=query,
            )

            | Q(
                seller__username__icontains=query,
            )
        )


    # --------------------------------------------------------
    # Category filter
    # --------------------------------------------------------

    valid_categories = {
        value
        for value, label in Product.CATEGORY_CHOICES
    }

    if category in valid_categories:

        products = products.filter(
            category=category,
        )

    else:
        category = ""


    # --------------------------------------------------------
    # Ordering
    # --------------------------------------------------------

    products = products.order_by(
        "-published_at",
        "-created_at",
    )


    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    paginator = Paginator(
        products,
        9,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )


    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    context = {
        "products": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,

        "query": query,
        "category": category,

        "categories": Product.CATEGORY_CHOICES,
    }


    return render(
        request,
        "marketplace/index.html",
        context,
    )


# ============================================================
# PRODUCT DETAIL
# ============================================================

def detail(request, slug):
    """
    Display a publicly available product.
    """

    product = get_object_or_404(
        Product.objects.select_related(
            "seller",
        ),
        slug=slug,
        status=Product.STATUS_APPROVED,
        is_published=True,
    )


    context = {
        "product": product,
    }


    return render(
        request,
        "marketplace/detail.html",
        context,
    )


# ============================================================
# SELLER DASHBOARD
# ============================================================

@login_required
def seller_dashboard(request):
    """
    Display the current seller's products.

    Product creation and editing use separate views.
    """

    products = (
        Product.objects
        .filter(
            seller=request.user,
        )
        .order_by(
            "-created_at",
        )
    )


    context = {
        "products": products,
    }


    return render(
        request,
        "marketplace/seller_dashboard.html",
        context,
    )


# ============================================================
# CREATE PRODUCT
# ============================================================

@login_required
def product_create(request):
    """
    Allow an authenticated seller to submit a new product.

    Sellers cannot set:
    - seller
    - status
    - is_published
    - publication timestamps
    """

    if request.method == "POST":

        form = ProductForm(
            request.POST,
            request.FILES,
        )


        if form.is_valid():

            product = form.save(
                commit=False,
            )

            product.seller = request.user

            product.status = (
                Product.STATUS_PENDING
            )

            product.is_published = False

            product.published_at = None

            product.save()


            messages.success(
                request,
                _(
                    "Your product was submitted "
                    "for review."
                ),
            )


            return redirect(
                "marketplace:seller_dashboard"
            )


    else:

        form = ProductForm()


    context = {
        "form": form,
        "mode": "create",
    }


    return render(
        request,
        "marketplace/product_form.html",
        context,
    )


# ============================================================
# EDIT PRODUCT
# ============================================================

@login_required
def product_edit(request, pk):
    """
    Allow sellers to edit only their own product.

    Every seller edit returns the product to moderation.
    """

    product = get_object_or_404(
        Product,
        pk=pk,
        seller=request.user,
    )


    if request.method == "POST":

        form = ProductForm(
            request.POST,
            request.FILES,
            instance=product,
        )


        if form.is_valid():

            product = form.save(
                commit=False,
            )


            # ------------------------------------------------
            # Editing invalidates previous public approval.
            # ------------------------------------------------

            product.status = (
                Product.STATUS_PENDING
            )

            product.is_published = False

            product.published_at = None

            product.save()


            messages.success(
                request,
                _(
                    "Your changes were saved. "
                    "The product has been returned "
                    "to the review queue."
                ),
            )


            return redirect(
                "marketplace:seller_dashboard"
            )


    else:

        form = ProductForm(
            instance=product,
        )


    context = {
        "form": form,
        "product": product,
        "mode": "edit",
    }


    return render(
        request,
        "marketplace/product_form.html",
        context,
    )


# ============================================================
# REVIEW QUEUE
# ============================================================

@staff_member_required
def review_queue(request):
    """
    Display products waiting for moderation.
    """

    pending_products = (
        Product.objects
        .filter(
            status=Product.STATUS_PENDING,
        )
        .select_related(
            "seller",
        )
        .order_by(
            "created_at",
        )
    )


    paginator = Paginator(
        pending_products,
        20,
    )

    page_obj = paginator.get_page(
        request.GET.get("page"),
    )


    context = {
        "pending_products": page_obj,
        "page_obj": page_obj,
    }


    return render(
        request,
        "marketplace/review_queue.html",
        context,
    )


# ============================================================
# REVIEW PRODUCT
# ============================================================

@staff_member_required
def review_product(request, pk):
    """
    Review one pending product.

    The decision is taken exclusively from ProductReviewForm
    and is submitted via POST.
    """

    product = get_object_or_404(
        Product.objects.select_related(
            "seller",
        ),
        pk=pk,
        status=Product.STATUS_PENDING,
    )


    if request.method == "POST":

        review_form = ProductReviewForm(
            request.POST,
        )


        if review_form.is_valid():

            with transaction.atomic():

                # --------------------------------------------
                # Save immutable review history
                # --------------------------------------------

                review = review_form.save(
                    commit=False,
                )

                review.product = product

                review.moderator = request.user

                review.save()


                decision = review.decision


                # --------------------------------------------
                # APPROVED
                # --------------------------------------------

                if (
                    decision
                    == ProductReview.DECISION_APPROVED
                ):

                    product.status = (
                        Product.STATUS_APPROVED
                    )

                    # Approval does not automatically publish.
                    product.is_published = False

                    product.published_at = None


                    messages.success(
                        request,
                        _(
                            "The product was approved. "
                            "It can now be published "
                            "by an administrator."
                        ),
                    )


                # --------------------------------------------
                # REJECTED
                # --------------------------------------------

                elif (
                    decision
                    == ProductReview.DECISION_REJECTED
                ):

                    product.status = (
                        Product.STATUS_REJECTED
                    )

                    product.is_published = False

                    product.published_at = None


                    messages.warning(
                        request,
                        _(
                            "The product was rejected."
                        ),
                    )


                # --------------------------------------------
                # CHANGES REQUESTED
                # --------------------------------------------

                elif (
                    decision
                    == ProductReview.DECISION_CHANGES
                ):

                    # Keep it out of the public marketplace.
                    # Rejected state allows the seller to
                    # clearly see that action is required.

                    product.status = (
                        Product.STATUS_REJECTED
                    )

                    product.is_published = False

                    product.published_at = None


                    messages.info(
                        request,
                        _(
                            "Changes were requested "
                            "from the seller."
                        ),
                    )


                product.save()


            return redirect(
                "marketplace:review_queue"
            )


    else:

        review_form = ProductReviewForm()


    # --------------------------------------------------------
    # Previous moderation history
    # --------------------------------------------------------

    review_history = (
        product.reviews
        .select_related(
            "moderator",
        )
        .order_by(
            "-reviewed_at",
        )
    )


    context = {
        "product": product,
        "review_form": review_form,
        "review_history": review_history,
    }


    return render(
        request,
        "marketplace/review_form.html",
        context,
    )