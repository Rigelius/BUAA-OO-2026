import com.oocourse.library2.LibraryBookId;
import com.oocourse.library2.LibraryBookIsbn;
import com.oocourse.library2.LibraryBookState;
import com.oocourse.library2.LibraryTrace;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;

public class Bookshelf {
    private final HashMap<LibraryBookIsbn, ArrayList<Book>> books = new HashMap<>();
    private final HashMap<LibraryBookId, Book> bookRecords = new HashMap<>();
    private final TreasuredBookshelf treasuredBookshelf;

    public Bookshelf(Map<LibraryBookIsbn, Integer> bookList,
            TreasuredBookshelf treasuredBookshelf) {
        this.treasuredBookshelf = treasuredBookshelf;
        for (Map.Entry<LibraryBookIsbn, Integer> entry : bookList.entrySet()) {
            LibraryBookIsbn isbn = entry.getKey();
            books.put(isbn, new ArrayList<>());
            for (int i = 1; i <= entry.getValue(); i++) {
                String copyId = String.format("%02d", i);
                LibraryBookId bookId = new LibraryBookId(isbn.getType(), isbn.getUid(), copyId);
                Book book = new Book(bookId);
                books.get(isbn).add(book);
                bookRecords.put(bookId, book);
            }
        }
    }

    public Book takeBook(LibraryBookIsbn isbn) {
        if (!books.get(isbn).isEmpty()) {
            return books.get(isbn).remove(0);
        }
        return treasuredBookshelf.takeBook(isbn);
    }

    public void putBook(Book book) {
        putBook(book, book.getState());
    }

    public void putBook(Book book, LibraryBookState state) {
        if (state == LibraryBookState.TREASURED_BOOKSHELF) {
            treasuredBookshelf.putBook(book);
        } else {
            books.get(book.getIsbn()).add(book);
        }
    }

    public boolean hasBook(LibraryBookIsbn isbn) {
        return !books.get(isbn).isEmpty() || treasuredBookshelf.hasBook(isbn);
    }

    public ArrayList<Book> arrangeTreasuredBooks(HashSet<LibraryBookIsbn> treasuredIsbns) {
        ArrayList<Book> movedBooks = new ArrayList<>();
        for (LibraryBookIsbn isbn : books.keySet()) {
            if (!treasuredIsbns.contains(isbn)) {
                continue;
            }
            ArrayList<Book> normalList = books.get(isbn);
            movedBooks.addAll(normalList);
            for (Book book : normalList) {
                treasuredBookshelf.putBook(book);
            }
            normalList.clear();
        }
        return movedBooks;
    }

    public ArrayList<Book> arrangeNormalBooks(HashSet<LibraryBookIsbn> treasuredIsbns) {
        ArrayList<Book> movedBooks = treasuredBookshelf.removeNormalBooks(treasuredIsbns);
        for (Book book : movedBooks) {
            books.get(book.getIsbn()).add(book);
        }
        return movedBooks;
    }

    public ArrayList<LibraryTrace> query(LibraryBookId bookCopyId) {
        return bookRecords.get(bookCopyId).queryMovingTrace();
    }

    public Book getBookRecord(LibraryBookId bookCopyId) {
        return bookRecords.get(bookCopyId);
    }
}
