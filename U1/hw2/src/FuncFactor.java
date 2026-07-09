import java.util.HashMap;
import java.util.Map;

public class FuncFactor implements Factor {
    private final Factor argument;
    private final FuncReg.FuncDef funcDef;

    public FuncFactor(Factor argument, FuncReg.FuncDef funcDef) {
        this.argument = argument;
        this.funcDef = funcDef;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        Poly arg = argument.toPoly(vars);
        Map<String, Poly> newVars = new HashMap<>();
        newVars.put("x", arg);
        return funcDef.getBodyExpr().toPoly(newVars);
    }
}