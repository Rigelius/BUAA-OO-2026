import com.oocourse.library3.LibraryCloseCmd;
import com.oocourse.library3.LibraryCommand;
import com.oocourse.library3.LibraryIO;
import com.oocourse.library3.LibraryOpenCmd;
import com.oocourse.library3.LibraryReqCmd;
import com.oocourse.library3.LibraryQcsCmd;
import com.oocourse.library3.LibraryBookIsbn;

import java.util.Map;

public class MainClass {
    public static void main(String[] args) {
        Map<LibraryBookIsbn, Integer> bookList = LibraryIO.SCANNER.getInventory();
        LibraryManager library = new LibraryManager(bookList);

        while (true) {
            LibraryCommand command = LibraryIO.SCANNER.nextCommand();
            if (command == null) {
                break;
            } else if (command instanceof LibraryOpenCmd) {
                library.open(command.getDate());
            } else if (command instanceof LibraryCloseCmd) {
                library.close(command.getDate());
            } else if (command instanceof LibraryQcsCmd) {
                library.queryCreditScore((LibraryQcsCmd) command);
            } else {
                library.serve((LibraryReqCmd) command);
            }
        }
    }

    public void orderNewBook() {}

    public void getOrderedBook() {}
}
