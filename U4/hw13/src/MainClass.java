import com.oocourse.library1.LibraryCloseCmd;
import com.oocourse.library1.LibraryCommand;
import com.oocourse.library1.LibraryIO;
import com.oocourse.library1.LibraryOpenCmd;
import com.oocourse.library1.LibraryReqCmd;
import com.oocourse.library1.LibraryBookIsbn;

import java.util.Map;

public class MainClass {
    public static void main(String[] args) {
        Map<LibraryBookIsbn, Integer> bookList = LibraryIO.SCANNER.getInventory();
        Library library = new Library(bookList);

        while (true) {
            LibraryCommand command = LibraryIO.SCANNER.nextCommand();
            if (command == null) {
                break;
            } else if (command instanceof LibraryOpenCmd) {
                library.open(command.getDate());
            } else if (command instanceof LibraryCloseCmd) {
                library.close(command.getDate());
            } else {
                library.serve((LibraryReqCmd) command);
            }
        }
    }
}
