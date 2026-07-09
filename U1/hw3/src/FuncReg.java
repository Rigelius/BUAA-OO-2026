import java.math.BigInteger;

public final class FuncReg {

    private FuncDef funcDef;

    private RecDef recDef;

    public FuncDef getFuncDef() {
        return funcDef;
    }

    public void setFuncDef(FuncDef funcDef) {
        this.funcDef = funcDef;
    }

    public RecDef getRecDef() {
        return recDef;
    }

    public void setRecDef(RecDef recDef) {
        this.recDef = recDef;
    }

    public static class FuncDef {

        private Expr bodyExpr;

        public FuncDef(Expr bodyExpr) {
            this.bodyExpr = bodyExpr;
        }

        public Expr getBodyExpr() {
            return bodyExpr;
        }
    }

    public static class RecDef {

        private Expr f0Body;
        private Expr f1Body;
        private BigInteger c1;
        private Factor arg1;
        private BigInteger c2;
        private Factor arg2;
        private Expr extraBody;

        public RecDef() {
        }

        public Expr getF0Body() {
            return f0Body;
        }

        public void setF0Body(Expr f0Body) {
            this.f0Body = f0Body;
        }

        public Expr getF1Body() {
            return f1Body;
        }

        public void setF1Body(Expr f1Body) {
            this.f1Body = f1Body;
        }

        public BigInteger getC1() {
            return c1;
        }

        public void setC1(BigInteger c1) {
            this.c1 = c1;
        }

        public Factor getArg1() {
            return arg1;
        }

        public void setArg1(Factor arg1) {
            this.arg1 = arg1;
        }

        public BigInteger getC2() {
            return c2;
        }

        public void setC2(BigInteger c2) {
            this.c2 = c2;
        }

        public Factor getArg2() {
            return arg2;
        }

        public void setArg2(Factor arg2) {
            this.arg2 = arg2;
        }

        public Expr getExtraBody() {
            return extraBody;
        }

        public void setExtraBody(Expr extraBody) {
            this.extraBody = extraBody;
        }
    }
}