import com.oocourse.library3.LibraryBookId;
import com.oocourse.library3.LibraryBookIsbn;
import com.oocourse.library3.LibraryBookState;
import com.oocourse.library3.LibraryTrace;

import java.time.LocalDate;
import java.util.ArrayList;

public class Book {
    private final LibraryBookId bookCopyId;
    private final LibraryBookIsbn isbn;
    private final LibraryBookIsbn.Type bookCategory;
    private LibraryBookState state;
    private final ArrayList<LibraryTrace> movingTrace = new ArrayList<>();
    private LocalDate dueDate;
    private boolean overduePenaltyApplied = false;

    public Book(LibraryBookId bookCopyId) {
        this.bookCopyId = bookCopyId;
        this.isbn = bookCopyId.getBookIsbn();
        this.bookCategory = bookCopyId.getType();
        this.state = LibraryBookState.BOOKSHELF;
    }

    public LibraryBookId getBookCopyId() {
        return bookCopyId;
    }

    public LibraryBookIsbn getIsbn() {
        return isbn;
    }

    public LibraryBookIsbn.Type getBookCategory() {
        return bookCategory;
    }

    public LibraryBookState getState() {
        return state;
    }

    public void moveTo(LibraryBookState to, LocalDate date) {
        movingTrace.add(new LibraryTrace(date, state, to));
        state = to;
    }

    public ArrayList<LibraryTrace> queryMovingTrace() {
        return movingTrace;
    }

    public LocalDate getDueDate() {
        return dueDate;
    }

    public void setDueDate(LocalDate dueDate) {
        this.dueDate = dueDate;
        this.overduePenaltyApplied = false;
    }

    public boolean isOverduePenaltyApplied() {
        return overduePenaltyApplied;
    }

    public void setOverduePenaltyApplied(boolean overduePenaltyApplied) {
        this.overduePenaltyApplied = overduePenaltyApplied;
    }
}
