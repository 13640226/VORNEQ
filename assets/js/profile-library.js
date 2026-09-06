class ProfileLibrary {
  constructor(manager) { this.manager = manager; this.activeShelf = 'all'; }
  init() {
    this.buttons = [...this.manager.root.querySelectorAll('[data-shelf]')];
    this.books = [...this.manager.root.querySelectorAll('[data-book-shelf]')];
    this.buttons.forEach((button) => button.addEventListener('click', () => this.selectShelf(button.dataset.shelf)));
  }
  selectShelf(shelf) {
    this.activeShelf = shelf;
    this.buttons.forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.shelf === shelf)));
    this.books.forEach((book) => {
      const shelves = (book.dataset.bookShelf || '').split(' ');
      book.hidden = shelf !== 'all' && !shelves.includes(shelf);
    });
  }
}
window.ProfileLibrary = ProfileLibrary;
